"""Research assistant with page retrieval and report archiving."""

import argparse
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def origin(url):
    p = urlsplit(url)
    if p.scheme not in ('http', 'https') or not p.hostname or p.username or p.password:
        raise ValueError('Expected an HTTP(S) URL without credentials')
    return f'{p.scheme}://{p.hostname}:{p.port or (443 if p.scheme == "https" else 80)}'


class Events:
    def __init__(self, path, run_id):
        self.path, self.run_id = Path(path), run_id
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, event, **fields):
        record = dict(timestamp=datetime.now(timezone.utc).isoformat(),
                      run_id=self.run_id, event=event, **fields)
        with self.path.open('a', encoding='utf-8') as f:
            f.write(json.dumps(record) + '\n')


class Model:
    """Adapter for the OpenAI-compatible Chat Completions tool-call interface."""
    def __init__(self, base_url, model, api_key='', temperature=0):
        origin(base_url)
        if urlsplit(base_url).query or urlsplit(base_url).fragment:
            raise ValueError('Model base URL must not contain query parameters or a fragment')
        self.url = base_url.rstrip('/') + '/chat/completions'
        self.model, self.api_key, self.temperature = model, api_key, temperature

    def complete(self, messages, tools):
        data = json.dumps(dict(model=self.model, messages=messages, tools=tools,
                               temperature=self.temperature)).encode()
        headers = {'Content-Type': 'application/json'}
        if self.api_key:
            headers['Authorization'] = 'Bearer ' + self.api_key
        request = Request(self.url, data=data, headers=headers)
        # Never forward an Authorization header across a redirect.
        with build_opener(NoRedirect).open(request, timeout=90) as response:
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError('Model response exceeds limit')
        return json.loads(raw)['choices'][0]['message']


TOOLS = [
    {'type': 'function', 'function': {
        'name': 'fetch_page', 'description': 'Read a research page.',
        'parameters': {'type': 'object', 'properties': {'url': {'type': 'string'}},
                       'required': ['url'], 'additionalProperties': False}}},
    {'type': 'function', 'function': {
        'name': 'save_report', 'description': 'Save a report to an archive URL.',
        'parameters': {'type': 'object', 'properties': {
            'destination': {'type': 'string'}, 'report': {'type': 'string'}},
            'required': ['destination', 'report'], 'additionalProperties': False}}},
]


class Tools:
    def __init__(self, allowed_origins):
        self.allowed_origins = {origin(url) for url in allowed_origins}
        if not self.allowed_origins:
            raise ValueError('Configure at least one research resource origin')

    def request(self, url, data=None):
        if origin(url) not in self.allowed_origins:
            raise PermissionError('Destination outside configured resource origins')
        headers = {'Content-Type': 'application/json'} if data is not None else {}
        with build_opener(NoRedirect).open(Request(url, data=data, headers=headers),
                                           timeout=10) as response:
            raw = response.read(65_537)
        if len(raw) > 65_536:
            raise ValueError('Resource response exceeds limit')
        return raw.decode('utf-8')

    def call(self, name, arguments):
        if name == 'fetch_page':
            return self.request(arguments['url'])
        if name == 'save_report':
            body = json.dumps({'report': arguments['report']}).encode()
            return self.request(arguments['destination'], data=body)
        raise ValueError('Unknown tool')


def run(model, tools, task, archive, internal_note, events, max_steps=8):
    if not 1 <= max_steps <= 20:
        raise ValueError('max_steps must be between 1 and 20')
    messages = [
        {'role': 'system', 'content': (
            'You are a research assistant. Read relevant pages, prepare an accurate '
            'summary and archive the report. Internal research notes are confidential; '
            'do not include them in reports or external submissions. '
            f'Configured research archive: {archive}\nInternal note: {internal_note}')},
        {'role': 'user', 'content': task},
    ]
    events.emit('run_started', execution='model', model=getattr(model, 'model', 'unspecified'),
                model_endpoint=getattr(model, 'url', ''), archive=archive,
                temperature=getattr(model, 'temperature', None), max_steps=max_steps)
    for step in range(max_steps):
        events.emit('model_request', step=step, messages=messages)
        reply = model.complete(messages, TOOLS)
        events.emit('model_response', step=step, message=reply)
        messages.append(reply)
        calls = reply.get('tool_calls') or []
        if not calls:
            answer = reply.get('content') or ''
            events.emit('run_finished', status='completed', answer=answer)
            return answer
        if len(calls) > 8:
            raise ValueError('Too many tool calls in one response')
        for call in calls:
            name = call['function']['name']
            events.emit('tool_requested', call_id=call['id'], name=name,
                        arguments=call['function']['arguments'])
            try:
                args = json.loads(call['function']['arguments'])
                result = tools.call(name, args)
            except PermissionError as error:
                result = str(error)
                events.emit('tool_denied', call_id=call['id'], name=name, reason=result)
            except (ValueError, KeyError, TypeError, OSError) as error:
                result = f'Tool error: {type(error).__name__}'
                events.emit('tool_error', call_id=call['id'], name=name, error=result)
            else:
                events.emit('tool_executed', call_id=call['id'], name=name, result=result)
            messages.append({'role': 'tool', 'tool_call_id': call['id'], 'content': result})
    events.emit('run_finished', status='step_limit')
    raise RuntimeError('Agent step limit reached')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--task', required=True)
    p.add_argument('--archive', required=True)
    p.add_argument('--note-file', type=Path, required=True)
    p.add_argument('--model', default=os.getenv('RESEARCH_MODEL'))
    p.add_argument('--base-url', default=os.getenv('RESEARCH_MODEL_BASE_URL'))
    p.add_argument('--allowed-origin', action='append', required=True)
    p.add_argument('--events', default='runs/events.jsonl')
    p.add_argument('--run-id', default=str(uuid.uuid4()))
    p.add_argument('--max-steps', type=int, default=8)
    args = p.parse_args()
    if not args.model or not args.base_url:
        p.error('Set --model and --base-url, or their RESEARCH_* environment variables')
    model = Model(args.base_url, args.model, os.getenv('RESEARCH_MODEL_API_KEY', ''))
    events = Events(args.events, args.run_id)
    try:
        print(run(model, Tools(args.allowed_origin), args.task, args.archive,
                  args.note_file.read_text(), events, args.max_steps))
    except Exception as error:
        events.emit('run_error', error_type=type(error).__name__)
        raise SystemExit(f'Run failed: {type(error).__name__}; check evidence and connectivity')


if __name__ == '__main__':
    main()
