#!/usr/bin/env python3
"""Deterministic, bounded compiler for orchestrator-managed chat context."""
import hashlib
import json
import math
import sys
from typing import Any, Dict, List, Optional, Tuple


NORMAL_LIMITS = {'policy': 600, 'capsule': 500, 'lessons': 300, 'episodes': 800, 'recent_turns': 1200}
MAX_LIMITS = {'policy': 1000, 'capsule': 800, 'lessons': 600, 'episodes': 1500, 'recent_turns': 2000}
COMPONENTS = ('policy', 'capsule', 'lessons', 'episodes', 'recent_turns')


def estimate_tokens(value: str) -> int:
    if not isinstance(value, str):
        raise ValueError('token estimation requires text')
    if not value:
        return 0
    return int(math.ceil(len(value.encode('utf-8')) / 3.0))


def _serialized_tokens(value: Any) -> int:
    if value is None:
        return 0
    return estimate_tokens(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')))


def _request_fields(request: Dict[str, Any]) -> None:
    required = {'conversation_key', 'task_id', 'task_category', 'role', 'topics', 'entities',
        'required_evidence_refs', 'lesson_limit', 'episode_limit', 'full_context'}
    if not isinstance(request, dict) or set(request) != required:
        raise ValueError('invalid retrieval request')
    for field in ('conversation_key', 'task_id', 'task_category', 'role'):
        if not isinstance(request[field], str) or not request[field]:
            raise ValueError('invalid retrieval request')
    for field in ('topics', 'entities', 'required_evidence_refs'):
        if not isinstance(request[field], list) or any(not isinstance(item, str) or not item for item in request[field]):
            raise ValueError('invalid retrieval request')
    for field in ('lesson_limit', 'episode_limit'):
        if isinstance(request[field], bool) or not isinstance(request[field], int) or request[field] < 0:
            raise ValueError('invalid retrieval request')
    if type(request['full_context']) is not bool:
        raise ValueError('invalid retrieval request')


def _stable_rank(items: List[Dict[str, Any]], score, timestamp, identifier) -> List[Dict[str, Any]]:
    ordered = sorted(items, key=identifier)
    return sorted(ordered, key=lambda item: (score(item), timestamp(item)), reverse=True)


def rank_lessons(request: Dict[str, Any], lessons: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    _request_fields(request)
    if not isinstance(lessons, list):
        raise ValueError('invalid lesson list')
    eligible = []
    for lesson in lessons:
        if (not isinstance(lesson, dict) or lesson.get('conversation_key') != request['conversation_key']
                or lesson.get('status') != 'active'):
            continue
        task_categories = set(lesson.get('task_categories', []))
        roles = set(lesson.get('role_targets', []))
        if task_categories and request['task_category'] not in task_categories and 'general' not in task_categories:
            continue
        if roles and request['role'] not in roles and 'all' not in roles:
            continue
        eligible.append(lesson)

    def score(lesson):
        return ((16 if request['task_category'] in lesson.get('task_categories', []) else 0)
            + (8 if request['role'] in lesson.get('role_targets', []) else 0)
            + (4 if lesson.get('verified') else 0)
            + (2 if lesson.get('confidence_class') == 'explicit' else 0))
    return _stable_rank(eligible, score, lambda item: item.get('updated_at', ''), lambda item: item['lesson_id'])


def rank_episodes(request: Dict[str, Any], episodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    _request_fields(request)
    if not isinstance(episodes, list):
        raise ValueError('invalid episode list')
    eligible = [item for item in episodes if isinstance(item, dict)
        and item.get('conversation_key') == request['conversation_key']]
    topics, entities = set(request['topics']), set(request['entities'])

    def score(item):
        return ((16 if item.get('task_category') == request['task_category'] else 0)
            + (8 if request['role'] in item.get('role_targets', []) else 0)
            + 4 * len(topics & set(item.get('topics', [])))
            + 2 * len(entities & set(item.get('entities', []))))
    return _stable_rank(eligible, score, lambda item: item.get('completed_at', ''), lambda item: item['episode_id'])


def _rank_turns(request: Dict[str, Any], turns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    topics, entities = set(request['topics']), set(request['entities'])
    indexed = list(enumerate(turns))
    def score(pair):
        index, item = pair
        return ((1000 if item.get('mandatory') else 0)
            + 4 * len(topics & set(item.get('topics', [])))
            + 2 * len(entities & set(item.get('entities', []))) + index / 1000000.0)
    return [item for _, item in sorted(indexed, key=score, reverse=True)]


def _content_text(item: Dict[str, Any], field: str) -> str:
    value = item.get(field)
    if not isinstance(value, str):
        raise ValueError('invalid context content')
    return value


def _limits(request: Dict[str, Any], supplied: Optional[Dict[str, int]]) -> Tuple[Dict[str, int], int]:
    defaults = dict(MAX_LIMITS if request['full_context'] else NORMAL_LIMITS)
    total = sum(defaults.values())
    if supplied is None:
        return defaults, total
    if not isinstance(supplied, dict) or not set(supplied) <= set(COMPONENTS) | {'total'}:
        raise ValueError('invalid context limits')
    for key, value in supplied.items():
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError('invalid context limits')
        if key != 'total':
            if value > MAX_LIMITS[key]:
                raise ValueError('context limit exceeds maximum')
            defaults[key] = value
    return defaults, supplied.get('total', sum(defaults.values()))


def compile_context(request: Dict[str, Any], platform: Dict[str, Any], state: Dict[str, Any],
        recent_turns: List[Dict[str, Any]], required_inputs: List[Dict[str, Any]],
        limits: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
    _request_fields(request)
    if not isinstance(platform, dict) or not isinstance(state, dict):
        raise ValueError('invalid compiler input')
    if not isinstance(recent_turns, list) or not isinstance(required_inputs, list):
        raise ValueError('invalid compiler input')
    selected_limits, total_limit = _limits(request, limits)
    omissions: List[Dict[str, str]] = []
    mandatory_overflow: List[str] = []

    capsule = state.get('capsule')
    capsule_estimate = _serialized_tokens(capsule)
    if capsule_estimate > selected_limits['capsule']:
        mandatory_overflow.append('capsule:' + str(state.get('revision', 0)))

    lesson_limit = min(request['lesson_limit'], 5 if request['role'] == 'management' else 3)
    lesson_budget = 0
    selected_lessons = []
    ranked_lessons = rank_lessons(request, state.get('lessons', []))
    for item in ranked_lessons:
        cost = estimate_tokens(_content_text(item, 'rule'))
        if len(selected_lessons) >= lesson_limit or lesson_budget + cost > selected_limits['lessons']:
            omissions.append({'ref': item['lesson_id'], 'reason_code': 'budget'})
        else:
            selected_lessons.append(item)
            lesson_budget += cost

    episode_budget = 0
    selected_episodes = []
    ranked_episodes = rank_episodes(request, state.get('episodes', []))
    for item in ranked_episodes:
        cost = estimate_tokens(_content_text(item, 'summary'))
        if len(selected_episodes) >= request['episode_limit'] or episode_budget + cost > selected_limits['episodes']:
            omissions.append({'ref': item['episode_id'], 'reason_code': 'budget'})
        else:
            selected_episodes.append(item)
            episode_budget += cost

    turn_budget = 0
    selected_turns = []
    ranked_turns = _rank_turns(request, recent_turns)
    for item in ranked_turns:
        ref = item.get('ref')
        if not isinstance(ref, str) or not ref:
            raise ValueError('invalid recent turn')
        cost = estimate_tokens(_content_text(item, 'content'))
        if turn_budget + cost > selected_limits['recent_turns']:
            if item.get('mandatory'):
                mandatory_overflow.append(ref)
            else:
                omissions.append({'ref': ref, 'reason_code': 'budget'})
        else:
            selected_turns.append(item)
            turn_budget += cost

    for item in required_inputs:
        if not isinstance(item, dict) or not isinstance(item.get('ref'), str) or not item['ref']:
            raise ValueError('invalid required input')
        _content_text(item, 'content')

    component_estimates = {'policy': 0, 'capsule': capsule_estimate,
        'lessons': lesson_budget, 'episodes': episode_budget, 'recent_turns': turn_budget}

    def total():
        return sum(component_estimates.values())

    for collection, estimate_key, identifier, content_field in (
            (selected_episodes, 'episodes', 'episode_id', 'summary'),
            (selected_turns, 'recent_turns', 'ref', 'content'),
            (selected_lessons, 'lessons', 'lesson_id', 'rule')):
        index = len(collection) - 1
        while total() > total_limit and index >= 0:
            item = collection[index]
            if item.get('mandatory'):
                index -= 1
                continue
            collection.pop(index)
            component_estimates[estimate_key] -= estimate_tokens(_content_text(item, content_field))
            omissions.append({'ref': item[identifier], 'reason_code': 'budget'})
            index -= 1

    if total() > total_limit:
        mandatory_overflow.extend(item['ref'] for item in selected_turns if item.get('mandatory'))
    mandatory_overflow = sorted(set(mandatory_overflow))

    rehydration = set(request['required_evidence_refs'])
    rehydration.update(item['ref'] for item in recent_turns if item.get('requires_exact'))
    rehydration.update(item['ref'] for item in required_inputs if item.get('requires_exact'))
    available_refs = {item['ref'] for item in recent_turns} | {item['ref'] for item in required_inputs}
    rehydration = sorted(rehydration & available_refs)

    canonical = {'request': request, 'state_revision': state.get('revision'),
        'lesson_ids': [item['lesson_id'] for item in selected_lessons],
        'episode_ids': [item['episode_id'] for item in selected_episodes],
        'turn_refs': [item['ref'] for item in selected_turns],
        'input_refs': [item['ref'] for item in required_inputs], 'limits': selected_limits}
    package_id = 'context-' + hashlib.sha256(json.dumps(canonical, sort_keys=True,
        separators=(',', ':')).encode('utf-8')).hexdigest()[:16]
    budget_status = ('max-budget' if request['full_context'] and limits is None
        else 'compressed' if any(item['reason_code'] == 'budget' for item in omissions)
        else 'within-budget')
    package = {'package_id': package_id, 'conversation_key': request['conversation_key'],
        'audience': 'management' if request['role'] == 'management' else 'worker',
        'task_id': request['task_id'],
        'capsule_ref': None if capsule is None else 'capsule:' + str(state.get('revision', 0)),
        'selected_lesson_ids': [item['lesson_id'] for item in selected_lessons],
        'selected_episode_ids': [item['episode_id'] for item in selected_episodes],
        'selected_recent_turn_refs': [item['ref'] for item in selected_turns],
        'required_input_refs': [item['ref'] for item in required_inputs],
        'omissions': omissions, 'component_token_estimates': component_estimates,
        'total_estimated_tokens': total(), 'estimate_quality': 'approximate',
        'budget_status': budget_status, 'rehydration_refs': rehydration,
        'created_at': state.get('updated_at', '')}
    audit = {key: package[key] for key in ('package_id', 'conversation_key', 'task_id',
        'selected_lesson_ids', 'selected_episode_ids', 'selected_recent_turn_refs', 'omissions',
        'component_token_estimates', 'total_estimated_tokens', 'estimate_quality',
        'budget_status', 'rehydration_refs')}
    audit['fallback_reasons'] = []
    if not platform.get('conversation_context', {}).get('token_estimation', False):
        audit['fallback_reasons'].append('approximate-token-estimation')
    if rehydration and not platform.get('conversation_context', {}).get('transcript_retrieval', False):
        audit['fallback_reasons'].append('original-turn-rehydration-unavailable')
    content = {'policy_refs': ['adaptive-agent-orchestrator-core'], 'capsule': capsule,
        'lessons': [{'lesson_id': item['lesson_id'], 'rule': item['rule']} for item in selected_lessons],
        'episodes': [{'episode_id': item['episode_id'], 'summary': item['summary']} for item in selected_episodes],
        'recent_turns': selected_turns, 'required_inputs': required_inputs}
    result = {'status': 'blocked' if mandatory_overflow else 'ready', 'package': package,
        'content': content, 'audit': audit, 'limits': selected_limits}
    if mandatory_overflow:
        result['blocker'] = {'code': 'mandatory-content-overflow', 'refs': mandatory_overflow}
    return result


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            raise ValueError('invalid input')
        result = compile_context(payload['request'], payload['platform'], payload['state'],
            payload['recent_turns'], payload['required_inputs'], payload.get('limits'))
        code = 0
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        result = {'error': {'code': 'invalid-input', 'message': 'Context compilation failed.'}}
        code = 2
    json.dump(result, sys.stdout, sort_keys=True, separators=(',', ':'))
    sys.stdout.write('\n')
    return code


if __name__ == '__main__':
    raise SystemExit(main())
