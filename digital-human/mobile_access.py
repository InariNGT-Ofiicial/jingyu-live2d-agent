"""Capability link for the private phone test on the instance's HTTPS ingress."""
import hmac
import json
import re
import secrets
from pathlib import Path
from urllib.parse import urlsplit

from aiohttp import web
from settings import LOCAL

COOKIE = '__Host-jingyu-call'
LANDING = """<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>鲸语 · 私人试拨</title><p id="msg">请使用完整的私人试拨链接。</p><script>
const key=location.hash.slice(1);
if(key){document.querySelector('#msg').textContent='正在接通私人入口…';
fetch('/join',{method:'POST',body:key}).then(async r=>{if(!r.ok)throw Error();location.replace('/')})
.catch(()=>document.querySelector('#msg').textContent='试拨链接未能验证，请重新打开完整链接。')}
</script></html>"""


class MobileAccess:
    def __init__(self, root, audio):
        origin_file = LOCAL / 'mobile-origin.txt'
        self.origin = origin_file.read_text().strip() if origin_file.is_file() else None
        if not self.origin:
            return
        if not re.fullmatch(r'https://[a-z0-9.-]+(?::\d+)?', self.origin):
            raise ValueError('mobile-origin.txt needs an HTTPS origin')
        self.host = urlsplit(self.origin).netloc
        secret = LOCAL / 'mobile-invite'
        if not secret.exists():
            with secret.open('x') as f:
                secret.chmod(0o600)
                f.write(secrets.token_urlsafe(32))
        self.key = secret.read_text().strip()
        self.cookie = hmac.digest(self.key.encode(), b'mobile-session', 'sha256').hex()
        asset = root / 'web/motion-policy.json'
        policy = json.loads(asset.read_text())
        self.paths = {'/', '/client.js', '/config', '/ws'}
        self.paths.update('/audio/' + key + '.wav' for key in audio)
        self.paths.update('/motions/' + c['file'] for c in policy['clips'].values())
        if policy.get('mobileDirectory'):
            self.paths.update('/motions/'+policy['mobileDirectory']+'/'+name+'.mp4' for name in policy['clips'])
            self.paths.update('/motions/'+policy['mobileDirectory']+'/'+name+'-start.mp4' for name in ('front-breathe','h3-shoulders'))
        self.paths.add('/motions/phone-delivery-v2/anchor.webp')
        self.paths.update('/motions/phone/' + name for name in (
            'call.css', 'call.js', 'duplex.js', 'mobile-motion.js', 'motion-director.js', 'motion-player.js', 'motion-policy.json'))

    @staticmethod
    def public(req):
        return req.transport.get_extra_info('sockname')[1] == 6006

    @web.middleware
    async def guard(self, req, handler):
        if not self.public(req):
            return await handler(req)
        if not self.origin:
            raise web.HTTPForbidden()
        if req.path == '/join' and req.method == 'POST':
            if req.headers.get('Origin') != self.origin or not hmac.compare_digest(await req.read(), self.key.encode()):
                raise web.HTTPForbidden()
            r = web.Response(status=204, headers={'Cache-Control':'no-store'})
            r.set_cookie(COOKIE, self.cookie, secure=True, httponly=True, samesite='Strict', path='/', max_age=86400)
            return r
        if not hmac.compare_digest(req.cookies.get(COOKIE, '').encode(), self.cookie.encode()):
            if req.path == '/' and req.method == 'GET':
                return web.Response(text=LANDING, content_type='text/html', headers={'Cache-Control':'no-store','Referrer-Policy':'no-referrer'})
            raise web.HTTPForbidden()
        if req.method not in ('GET','HEAD') or req.path not in self.paths:
            raise web.HTTPNotFound()
        if req.path == '/ws' and req.headers.get('Origin') != self.origin:
            raise web.HTTPForbidden()
        response = await handler(req)
        if req.path == '/' or req.path.endswith('.js'):
            response.headers['Cache-Control'] = 'private, no-store'
        return response
