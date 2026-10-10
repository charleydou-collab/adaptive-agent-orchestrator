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
TEXT_LIMITS = {'conversation_key': 128, 'task_id': 128,
    'task_category': 128, 'role': 128}
COLLECTION_LIMITS = {'topics': (64, 256), 'entities': (64, 256),
    'required_evidence_refs': (128, 512), 'applicability_facts': (64, 512)}


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
        'required_evidence_refs', 'applicability_facts', 'lesson_limit', 'episode_limit',
        'full_context'}
    if not isinstance(request, dict) or set(request) != required:
        raise ValueError('invalid retrieval request')
    for field, maximum in TEXT_LIMITS.items():
        if (not isinstance(request[field], str) or not request[field]
                or len(request[field]) > maximum):
            raise ValueError('invalid retrieval request')
    for field, (max_items, max_length) in COLLECTION_LIMITS.items():
        value = request[field]
        if (not isinstance(value, list) or len(value) > max_items
                or any(not isinstance(item, str) or not item or len(item) > max_length
                    for item in value)):
            raise ValueError('invalid retrieval request')
        if len(set(value)) != len(value):
            raise ValueError('invalid retrieval request')
    for field, maximum in (('lesson_limit', 5), ('episode_limit', 20)):
        if (isinstance(request[field], bool) or not isinstance(request[field], int)
                or not 0 <= request[field] <= maximum):
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
    facts = set(request['applicability_facts'])
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
        conditions = lesson.get('conditions', [])
        exceptions = lesson.get('exceptions', [])
        if (not isinstance(conditions, list) or not isinstance(exceptions, list)
                or any(not isinstance(item, str) for item in conditions + exceptions)):
            continue
        if not set(conditions) <= facts or set(exceptions) & facts:
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
        and item.get('conversation_key') == request['conversation_key']
        and (request['role'] == 'management'
            or request['role'] in item.get('role_targets', [])
            or 'all' in item.get('role_targets', []))]
    topics, entities = set(request['topics']), set(request['entities'])

    def score(item):
        return ((16 if item.get('task_category') == request['task_category'] else 0)
            + (8 if request['role'] in item.get('role_targets', []) else 0)
            + 4 * len(topics & set(item.get('topics', [])))
            + 2 * len(entities & set(item.get('entities', []))))
    return _stable_rank(eligible, score, lambda item: item.get('completed_at', ''), lambda item: item['episode_id'])


def _rank_turns(request: Dict[str, Any], turns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    topics, entities = set(request['topics']), set(request['entities'])
    indexed = [(index, item) for index, item in enumerate(turns)
        if (request['role'] == 'management'
            or request['role'] in item.get('role_targets', [])
            or 'all' in item.get('role_targets', []))]
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
    total_limit = supplied.get('total', sum(defaults.values()))
    if total_limit > sum(MAX_LIMITS.values()):
        raise ValueError('context limit exceeds maximum')
    return defaults, total_limit


def _state_conversation_key(state: Dict[str, Any]) -> str:
    scope = state.get('scope')
    if not isinstance(scope, dict):
        raise ValueError('invalid compiler input')
    adapter = scope.get('adapter')
    conversation_id = scope.get('conversation_id')
    if not isinstance(adapter, str) or not adapter or not isinstance(conversation_id, str) or not conversation_id:
        raise ValueError('invalid compiler input')
    return hashlib.sha256((adapter + '\0' + conversation_id).encode('utf-8')).hexdigest()


def _component_estimates(content: Dict[str, Any]) -> Dict[str, int]:
    return {
        'policy': _serialized_tokens(content['policy_refs']),
        'capsule': _serialized_tokens(content['capsule']),
        'lessons': _serialized_tokens(content['lessons']),
        'episodes': _serialized_tokens({'episodes': content['episodes'],
            'required_inputs': content['required_inputs']}),
        'recent_turns': _serialized_tokens(content['recent_turns']),
    }


def compile_context(request: Dict[str, Any], platform: Dict[str, Any], state: Dict[str, Any],
        recent_turns: List[Dict[str, Any]], required_inputs: List[Dict[str, Any]],
        limits: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
    _request_fields(request)
    if not isinstance(platform, dict) or not isinstance(state, dict):
        raise ValueError('invalid compiler input')
    if not isinstance(recent_turns, list) or not isinstance(required_inputs, list):
        raise ValueError('invalid compiler input')
    if _state_conversation_key(state) != request['conversation_key']:
        raise ValueError('conversation scope mismatch')
    stored_capsule = state.get('capsule')
    if stored_capsule is not None and (not isinstance(stored_capsule, dict)
            or stored_capsule.get('conversation_key') != request['conversation_key']):
        raise ValueError('capsule conversation mismatch')

    selected_limits, total_limit = _limits(request, limits)
    omissions: List[Dict[str, str]] = []
    mandatory_overflow: List[str] = []
    required_refs = set(request['required_evidence_refs'])
    is_management = request['role'] == 'management'

    policy_refs = ['adaptive-agent-orchestrator-core']
    if _serialized_tokens(policy_refs) > selected_limits['policy']:
        mandatory_overflow.append('policy:adaptive-agent-orchestrator-core')

    capsule = stored_capsule if is_management else None
    if _serialized_tokens(capsule) > selected_limits['capsule']:
        mandatory_overflow.append('capsule:' + str(state.get('revision', 0)))
        capsule = None

    lesson_limit = min(request['lesson_limit'], 5 if request['role'] == 'management' else 3)
    selected_lessons = []
    ranked_lessons = rank_lessons(request, state.get('lessons', []))
    for item in ranked_lessons:
        emitted = {'lesson_id': item['lesson_id'], 'rule': _content_text(item, 'rule')}
        if (len(selected_lessons) >= lesson_limit
                or _serialized_tokens(selected_lessons + [emitted]) > selected_limits['lessons']):
            omissions.append({'ref': item['lesson_id'], 'reason_code': 'budget'})
        else:
            selected_lessons.append(emitted)

    selected_episodes = []
    selected_inputs = []
    for item in required_inputs:
        if not isinstance(item, dict) or not isinstance(item.get('ref'), str) or not item['ref']:
            raise ValueError('invalid required input')
        _content_text(item, 'content')
        candidate = selected_inputs + [item]
        evidence_content = {'episodes': selected_episodes, 'required_inputs': candidate}
        if _serialized_tokens(evidence_content) > selected_limits['episodes']:
            mandatory_overflow.append(item['ref'])
        else:
            selected_inputs.append(item)

    ranked_episodes = rank_episodes(request, state.get('episodes', []))
    for item in ranked_episodes:
        emitted = {'episode_id': item['episode_id'], 'summary': _content_text(item, 'summary')}
        evidence_content = {'episodes': selected_episodes + [emitted],
            'required_inputs': selected_inputs}
        if (len(selected_episodes) >= request['episode_limit']
                or _serialized_tokens(evidence_content) > selected_limits['episodes']):
            omissions.append({'ref': item['episode_id'], 'reason_code': 'budget'})
        else:
            selected_episodes.append(emitted)

    selected_turns = []
    ranked_turns = _rank_turns(request, recent_turns)
    for item in ranked_turns:
        ref = item.get('ref')
        if not isinstance(ref, str) or not ref:
            raise ValueError('invalid recent turn')
        _content_text(item, 'content')
        is_required = bool(item.get('mandatory')) or ref in required_refs
        if _serialized_tokens(selected_turns + [item]) > selected_limits['recent_turns']:
            if is_required:
                mandatory_overflow.append(ref)
            else:
                omissions.append({'ref': ref, 'reason_code': 'budget'})
        else:
            selected_turns.append(item)

    content = {'policy_refs': policy_refs, 'capsule': capsule,
        'lessons': selected_lessons, 'episodes': selected_episodes,
        'recent_turns': selected_turns, 'required_inputs': selected_inputs}

    for collection, identifier in (
            (selected_episodes, 'episode_id'),
            (selected_turns, 'ref'),
            (selected_lessons, 'lesson_id')):
        index = len(collection) - 1
        while _serialized_tokens(content) > total_limit and index >= 0:
            item = collection[index]
            if (collection is selected_turns
                    and (item.get('mandatory') or item['ref'] in required_refs)):
                index -= 1
                continue
            collection.pop(index)
            omissions.append({'ref': item[identifier], 'reason_code': 'budget'})
            index -= 1

    if _serialized_tokens(content) > total_limit:
        mandatory_overflow.extend(item['ref'] for item in selected_turns
            if item.get('mandatory') or item['ref'] in required_refs)
        mandatory_overflow.extend(item['ref'] for item in selected_inputs)
        if capsule is not None:
            mandatory_overflow.append('capsule:' + str(state.get('revision', 0)))
        mandatory_overflow.append('policy:adaptive-agent-orchestrator-core')
    mandatory_overflow = sorted(set(mandatory_overflow))

    rehydration = set(request['required_evidence_refs'])
    rehydration.update(item['ref'] for item in ranked_turns if item.get('requires_exact'))
    rehydration.update(item['ref'] for item in required_inputs if item.get('requires_exact'))
    rehydration = sorted(rehydration)
    emitted_refs = ({item['ref'] for item in selected_turns}
        | {item['ref'] for item in selected_inputs})
    unavailable_rehydration = sorted(ref for ref in rehydration if ref not in emitted_refs)
    can_rehydrate = bool(platform.get('conversation_context', {}).get(
        'original_turn_rehydration', False))

    canonical = {'request': request, 'state_revision': state.get('revision'),
        'lesson_ids': [item['lesson_id'] for item in selected_lessons],
        'episode_ids': [item['episode_id'] for item in selected_episodes],
        'turn_refs': [item['ref'] for item in selected_turns],
        'input_refs': [item['ref'] for item in selected_inputs], 'limits': selected_limits}
    package_id = 'context-' + hashlib.sha256(json.dumps(canonical, sort_keys=True,
        separators=(',', ':')).encode('utf-8')).hexdigest()[:16]
    budget_status = ('max-budget' if request['full_context'] and limits is None
        else 'compressed' if any(item['reason_code'] == 'budget' for item in omissions)
        else 'within-budget')
    component_estimates = _component_estimates(content)
    total_estimate = _serialized_tokens(content)
    for component in COMPONENTS:
        if component_estimates[component] > selected_limits[component]:
            mandatory_overflow.append(component + ':fixed-overhead')
    mandatory_overflow = sorted(set(mandatory_overflow))
    package = {'package_id': package_id, 'conversation_key': request['conversation_key'],
        'audience': 'management' if request['role'] == 'management' else 'worker',
        'task_id': request['task_id'],
        'capsule_ref': None if capsule is None else 'capsule:' + str(state.get('revision', 0)),
        'selected_lesson_ids': [item['lesson_id'] for item in selected_lessons],
        'selected_episode_ids': [item['episode_id'] for item in selected_episodes],
        'selected_recent_turn_refs': [item['ref'] for item in selected_turns],
        'required_input_refs': [item['ref'] for item in selected_inputs],
        'omissions': omissions, 'component_token_estimates': component_estimates,
        'total_estimated_tokens': total_estimate, 'estimate_quality': 'approximate',
        'budget_status': budget_status, 'rehydration_refs': rehydration,
        'created_at': state.get('updated_at', '')}
    audit = {key: package[key] for key in ('package_id', 'conversation_key', 'task_id',
        'selected_lesson_ids', 'selected_episode_ids', 'selected_recent_turn_refs', 'omissions',
        'component_token_estimates', 'total_estimated_tokens', 'estimate_quality',
        'budget_status', 'rehydration_refs')}
    audit['fallback_reasons'] = []
    if not platform.get('conversation_context', {}).get('token_estimation', False):
        audit['fallback_reasons'].append('approximate-token-estimation')
    if unavailable_rehydration and not can_rehydrate:
        audit['fallback_reasons'].append('original-turn-rehydration-unavailable')
    unavailable_blocker = (sorted(required_refs - emitted_refs)
        if not can_rehydrate else [])
    result = {'status': 'blocked' if mandatory_overflow or unavailable_blocker else 'ready', 'package': package,
        'content': content, 'audit': audit, 'limits': selected_limits}
    if mandatory_overflow:
        result['blocker'] = {'code': 'mandatory-content-overflow', 'refs': mandatory_overflow}
    elif unavailable_blocker:
        result['blocker'] = {'code': 'required-evidence-unavailable',
            'refs': unavailable_blocker}
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
