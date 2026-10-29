"""Existing model configuration -> JSON action planner; never returns raw exceptions."""
import os
from urllib.parse import urlsplit
import requests


class PlannerError(Exception):
    pass


def endpoint(base, suffix):
    value = (base or '').strip().rstrip('/')
    if not value.startswith(('http://','https://')): value='https://'+value
    parsed=urlsplit(value)
    if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('模型地址必须为不含凭证、查询参数的HTTP地址')
    return value if parsed.path.endswith(suffix) else value+suffix


class JsonPlanner:
    def __init__(self, *, api_key=None, model=None, api_url=None, use_ollama=False,
                 ollama_url=None, ollama_model=None):
        self.api_key = api_key or os.environ.get('DEEPSEEK_API_KEY','').strip()
        self.use_ollama=use_ollama
        self.model=(ollama_model or 'deepseek-r1:latest') if use_ollama else (model or 'deepseek-flash')
        self.url=endpoint(ollama_url or 'http://localhost:11434','/api/chat') if use_ollama else endpoint(api_url or 'https://api.deepseek.com','/chat/completions')

    @property
    def configured(self): return self.use_ollama or bool(self.api_key)

    def __call__(self, messages, remaining):
        payload={'model':self.model,'messages':messages,'stream':False,'temperature':0.1}
        headers={'Content-Type':'application/json'}
        if self.use_ollama:
            payload['format']='json';payload['options']={'num_predict':2400}
        else:
            payload.update(max_tokens=2400, response_format={'type':'json_object'})
            headers['Authorization']='Bearer '+self.api_key
            if urlsplit(self.url).hostname=='api.deepseek.com':
                payload['thinking']={'type':'disabled'}
        try:
            # stream=True bounds response memory and allows a wall-time check while reading.
            import time
            deadline=time.monotonic()+min(remaining,35)
            with requests.post(self.url,json=payload,headers=headers,timeout=(min(5,remaining),min(30,remaining)),
                               stream=True,allow_redirects=False) as response:
                if response.status_code != 200: raise PlannerError('model_http_error')
                content=bytearray()
                for block in response.iter_content(1):
                    if time.monotonic()>=deadline: raise TimeoutError()
                    content.extend(block)
                    if len(content)>256000: raise PlannerError('model_response_too_large')
            import json
            data=json.loads(content)
            if self.use_ollama: return data['message']['content']
            if data['choices'][0].get('finish_reason') not in ('stop',None): raise PlannerError('truncated')
            return data['choices'][0]['message']['content']
        except requests.Timeout as exc: raise TimeoutError() from exc
        except (requests.RequestException,KeyError,IndexError) as exc: raise PlannerError('model_unavailable') from exc
