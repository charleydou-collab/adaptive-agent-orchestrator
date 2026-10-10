#!/usr/bin/env python3
"""Deterministic governance for chat-scoped learning candidates."""
from datetime import datetime, timezone
import hashlib
from typing import Any, Dict, List


CANDIDATE_FIELDS = {
    'candidate_id', 'conversation_key', 'rule', 'category', 'task_categories',
    'role_targets', 'conditions', 'exceptions', 'source_refs',
    'confidence_class', 'risk_class', 'verified', 'created_at',
}
CATEGORIES = {
    'preference', 'factual-correction', 'interpretation-rule', 'workflow-rule',
    'formatting-rule', 'failure-avoidance',
}
CONFIDENCE_CLASSES = {'explicit', 'verified', 'repeated', 'inferred'}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def _validate_string_list(value: Any, allow_empty: bool = True) -> None:
    if not isinstance(value, list) or (not allow_empty and not value):
        raise ValueError('invalid learning candidate')
    if any(not isinstance(item, str) or not item for item in value) or len(set(value)) != len(value):
        raise ValueError('invalid learning candidate')


def _validate_candidate(candidate: Dict[str, Any]) -> None:
    if not isinstance(candidate, dict) or set(candidate) != CANDIDATE_FIELDS:
        raise ValueError('invalid learning candidate')
    for field in ('candidate_id', 'conversation_key', 'rule', 'created_at'):
        if not isinstance(candidate[field], str) or not candidate[field]:
            raise ValueError('invalid learning candidate')
    if candidate['category'] not in CATEGORIES or candidate['confidence_class'] not in CONFIDENCE_CLASSES:
        raise ValueError('invalid learning candidate')
    if candidate['risk_class'] not in {'low', 'high'} or type(candidate['verified']) is not bool:
        raise ValueError('invalid learning candidate')
    for field in ('task_categories', 'role_targets', 'source_refs'):
        _validate_string_list(candidate[field], allow_empty=False)
    for field in ('conditions', 'exceptions'):
        _validate_string_list(candidate[field])


def _conflicts(candidate: Dict[str, Any], lesson: Dict[str, Any]) -> bool:
    return (lesson.get('status') == 'active'
        and lesson.get('conversation_key') == candidate['conversation_key']
        and lesson.get('category') == candidate['category']
        and bool(set(lesson.get('task_categories', [])) & set(candidate['task_categories']))
        and bool(set(lesson.get('role_targets', [])) & set(candidate['role_targets']))
        and lesson.get('rule') != candidate['rule'])


def activation_decision(candidate: Dict[str, Any], existing_lessons: List[Dict[str, Any]], corroboration_count: int) -> Dict[str, Any]:
    _validate_candidate(candidate)
    if not isinstance(existing_lessons, list) or isinstance(corroboration_count, bool) or not isinstance(corroboration_count, int) or corroboration_count < 0:
        raise ValueError('invalid activation input')
    conflicts = sorted(lesson['lesson_id'] for lesson in existing_lessons if _conflicts(candidate, lesson))

    if candidate['risk_class'] == 'high':
        action, status, reason, confirmation = 'propose', 'proposed', 'high-impact-confirmation', True
    elif candidate['category'] == 'factual-correction' and not candidate['verified']:
        action, status, reason, confirmation = 'propose', 'proposed', 'evidence-required', False
    elif candidate['category'] == 'factual-correction':
        action, status, reason, confirmation = 'activate', 'active', 'verified-factual-correction', False
    elif candidate['category'] == 'preference' and candidate['confidence_class'] == 'repeated' and corroboration_count >= 2:
        action, status, reason, confirmation = 'activate', 'active', 'repeated-preference', False
    elif candidate['confidence_class'] == 'explicit':
        action, status, reason, confirmation = 'activate', 'active', 'explicit-low-risk', False
    elif candidate['confidence_class'] == 'inferred':
        action, status, reason, confirmation = 'propose', 'proposed', 'inference-confirmation', True
    else:
        action, status, reason, confirmation = 'propose', 'proposed', 'insufficient-corroboration', False
    return {'action': action, 'status': status, 'reason_code': reason,
        'requires_confirmation': confirmation, 'conflicting_lesson_ids': conflicts}


def _state_conversation_key(state: Dict[str, Any]) -> str:
    if isinstance(state.get('conversation_key'), str):
        return state['conversation_key']
    scope = state.get('scope', {})
    adapter, conversation_id = scope.get('adapter'), scope.get('conversation_id')
    if not isinstance(adapter, str) or not adapter or not isinstance(conversation_id, str) or not conversation_id:
        raise ValueError('invalid conversation scope')
    return hashlib.sha256((adapter + '\0' + conversation_id).encode('utf-8')).hexdigest()


def apply_candidate(state: Dict[str, Any], candidate: Dict[str, Any], decision: Dict[str, Any]) -> str:
    _validate_candidate(candidate)
    if _state_conversation_key(state) != candidate['conversation_key']:
        raise ValueError('candidate belongs to another conversation')
    expected_decision_fields = {'action', 'status', 'reason_code', 'requires_confirmation', 'conflicting_lesson_ids'}
    if not isinstance(decision, dict) or set(decision) != expected_decision_fields:
        raise ValueError('invalid activation decision')
    if decision['action'] not in {'activate', 'propose'} or decision['status'] not in {'active', 'proposed'}:
        raise ValueError('invalid activation decision')
    if type(decision['requires_confirmation']) is not bool:
        raise ValueError('invalid activation decision')
    _validate_string_list(decision['conflicting_lesson_ids'])

    lessons = state.get('lessons')
    if not isinstance(lessons, list):
        raise ValueError('invalid lesson store')
    actual_conflicts = sorted(lesson['lesson_id'] for lesson in lessons if _conflicts(candidate, lesson))
    if actual_conflicts != decision['conflicting_lesson_ids']:
        raise ValueError('stale activation decision')
    lesson_id = 'lesson-' + candidate['candidate_id']
    if any(item.get('lesson_id') == lesson_id for item in lessons):
        raise ValueError('duplicate lesson')

    conflicting = [item for item in lessons if item.get('lesson_id') in actual_conflicts]
    if decision['status'] == 'active' and candidate['verified']:
        replacement_status = 'superseded'
    else:
        replacement_status = 'disputed'
    for item in conflicting:
        item['status'] = replacement_status
        item['updated_at'] = candidate['created_at']

    newest = None
    if conflicting:
        newest = max(conflicting, key=lambda item: (item.get('version', 0), item.get('created_at', ''), item['lesson_id']))
    version = max([item.get('version', 0) for item in conflicting] or [0]) + 1
    lesson = {key: value for key, value in candidate.items() if key != 'candidate_id'}
    lesson.update({'lesson_id': lesson_id, 'status': decision['status'], 'version': version,
        'supersedes': newest['lesson_id'] if newest else None, 'expires_at': None,
        'updated_at': candidate['created_at']})
    lessons.append(lesson)
    return lesson_id


def forget_lesson(state: Dict[str, Any], lesson_id: str) -> None:
    matches = [item for item in state.get('lessons', []) if item.get('lesson_id') == lesson_id]
    if len(matches) != 1:
        raise ValueError('lesson unavailable')
    matches[0]['status'] = 'forgotten'
    matches[0]['updated_at'] = _now()


def activate_lesson(state: Dict[str, Any], lesson_id: str, updated_at: str = None) -> None:
    """Confirm one proposal after rechecking current same-conversation conflicts."""
    timestamp = updated_at or _now()
    _instant(timestamp)
    matches = [item for item in state.get('lessons', [])
        if item.get('lesson_id') == lesson_id]
    if len(matches) != 1 or matches[0].get('status') != 'proposed':
        raise ValueError('lesson unavailable')
    lesson = matches[0]
    if lesson.get('category') == 'factual-correction' and not lesson.get('verified'):
        raise ValueError('evidence required')
    conflicts = [item for item in state['lessons']
        if item is not lesson and _conflicts(lesson, item)]
    newest = max(conflicts,
        key=lambda item: (item.get('version', 0), item.get('created_at', ''), item['lesson_id']),
        default=None)
    for item in conflicts:
        item['status'] = 'superseded'
        item['updated_at'] = timestamp
    lesson['status'] = 'active'
    lesson['version'] = max([lesson.get('version', 0)]
        + [item.get('version', 0) for item in conflicts]) + 1
    if newest is not None:
        lesson['supersedes'] = newest['lesson_id']
    lesson['updated_at'] = timestamp


def _instant(value: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError('invalid expiration')
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as error:
        raise ValueError('invalid expiration') from error


def expire_lessons(state: Dict[str, Any], now: str) -> List[str]:
    current = _instant(now)
    expired = []
    for lesson in state.get('lessons', []):
        expiration = lesson.get('expires_at')
        if lesson.get('status') == 'active' and expiration is not None and _instant(expiration) <= current:
            lesson['status'] = 'expired'
            lesson['updated_at'] = now
            expired.append(lesson['lesson_id'])
    return sorted(expired)
