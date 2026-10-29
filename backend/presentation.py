"""Presentation keys contain only bounded result positions, never database identifiers."""


def presentation_targets(results):
    targets = ['response']
    daily = next((i for i, r in enumerate(results) if r['tool'] == 'get_daily_briefing'), None)
    briefing = daily if daily is not None else next((i for i, r in enumerate(results) if r['tool'] == 'get_weather'), None)
    task = next((i for i, r in enumerate(results) if r['tool'] in ('list_tasks', 'manage_tasks', 'register_courses')), None)
    analysis = any(r['tool'] not in ('get_daily_briefing', 'get_weather', 'list_tasks', 'manage_tasks', 'register_courses') for r in results)
    for index, result in enumerate(results):
        tool, data = result['tool'], result['data']
        prefix = f'r{index}'
        if index == briefing and not analysis:
            targets.append(prefix + '.weather')
            if tool == 'get_daily_briefing':
                for name in ('classes', 'tasks'):
                    targets.append(prefix + '.' + name)
                    targets.extend(f'{prefix}.{name}.{i}' for i, row in enumerate(data.get(name, [])[:12 if name == 'classes' else 20])
                                   if name != 'tasks' or row.get('status') != 'done')
        elif index == task and (briefing is None or analysis) and tool in ('list_tasks', 'manage_tasks'):
            targets.append(prefix + '.tasks')
            targets.extend(f'{prefix}.tasks.{i}' for i in range(min(len(data.get('items', [])), 20)))
    return targets


def checked_segments(value, answer, results):
    if not isinstance(value, list) or not 1 <= len(value) <= 12 or not isinstance(answer, str) or len(answer) > 2000:
        return []
    allowed = presentation_targets(results)
    for segment in value:
        if (not isinstance(segment, dict) or set(segment) != {'text', 'target'} or
                not isinstance(segment['text'], str) or not segment['text'].strip() or
                not isinstance(segment['target'], str) or segment['target'] not in allowed):
            return []
    if ' '.join(' '.join(s['text'].split()) for s in value) != ' '.join(answer.split()):
        return []
    return value
