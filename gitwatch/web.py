import os
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException
from .clients import InputError, RemoteError
from .service import Watcher

def create_app(directory=None, watcher=None):
    app = Flask(__name__, static_folder='static')
    hosts = os.getenv('GITWATCH_TRUSTED_HOSTS','127.0.0.1,localhost').split(',')
    app.config.update(MAX_CONTENT_LENGTH=16384, TRUSTED_HOSTS=[h.strip() for h in hosts if h.strip()])
    watcher = watcher or Watcher(directory or os.getenv('GITWATCH_DATA', str(Path(__file__).resolve().parent.parent/'data')))
    app.extensions['watcher'] = watcher

    @app.before_request
    def protect_request():
        if request.method not in ('GET','HEAD','OPTIONS'):
            if request.headers.get('X-GitWatch') != '1' or request.headers.get('Sec-Fetch-Site') == 'cross-site':
                return jsonify(error='Запрос отклонён. Открой сайт напрямую и повтори.'),403
            origin = request.headers.get('Origin')
            if origin and origin != request.host_url.rstrip('/'):
                return jsonify(error='Запрос с другого сайта отклонён.'),403
            if not request.is_json:
                return jsonify(error='Ожидается JSON-запрос.'),415

    @app.after_request
    def security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'self'; object-src 'none'; base-uri 'self'; form-action 'self'"
        response.headers['Cache-Control'] = 'no-store' if request.path.startswith('/api/') else 'no-cache'
        return response

    @app.errorhandler(InputError)
    def input_error(exc):
        return jsonify(error=str(exc)),400

    @app.errorhandler(RemoteError)
    def remote_error(exc):
        return jsonify(error=str(exc),retry_at=exc.retry_at),502

    @app.errorhandler(HTTPException)
    def http_error(exc):
        return jsonify(error='Запрос не выполнен. Проверь адрес и данные.',status=exc.code),exc.code

    @app.errorhandler(Exception)
    def internal_error(exc):
        app.logger.error('Request failed: %s',type(exc).__name__)
        return jsonify(error='Не удалось выполнить запрос. Обнови страницу и повтори.'),500

    def body(allowed):
        data = request.get_json()
        if not isinstance(data,dict) or set(data)-set(allowed):
            raise InputError('Некорректный формат запроса. Обнови страницу.')
        return data

    @app.get('/')
    def index():
        return send_from_directory(Path(__file__).parent/'static', 'index.html')

    @app.get('/health')
    def health():
        return jsonify(ok=True,workers=bool(watcher.threads) and all(t.is_alive() for t in watcher.threads),version='1.0.0')

    @app.get('/api/state')
    def state():
        return jsonify(watcher.snapshot())

    @app.post('/api/repos')
    def add_repo():
        return jsonify(watcher.add_repo(body(('url','mode','branch','interval_minutes')))),201

    @app.patch('/api/repos/<int:repo_id>')
    def update_repo(repo_id):
        watcher.update_repo(repo_id,body(('mode','branch','interval_minutes','enabled','revision')))
        return jsonify(ok=True)

    @app.delete('/api/repos/<int:repo_id>')
    def remove_repo(repo_id):
        body(())
        watcher.remove_repo(repo_id)
        return jsonify(ok=True)

    @app.post('/api/repos/<int:repo_id>/check')
    def check_repo(repo_id):
        body(())
        watcher.request_check(repo_id)
        return jsonify(ok=True)

    @app.post('/api/check')
    def check_all():
        body(())
        watcher.request_check()
        return jsonify(ok=True)

    @app.put('/api/telegram')
    def telegram_settings():
        watcher.configure_telegram(body(('token','username','revision')))
        return jsonify(ok=True)

    @app.post('/api/telegram/test')
    def telegram_test():
        body(())
        watcher.test_telegram()
        return jsonify(ok=True)

    @app.post('/api/telegram/disconnect')
    def telegram_disconnect():
        body(())
        watcher.disconnect_telegram()
        return jsonify(ok=True)

    @app.put('/api/github')
    def github_settings():
        watcher.configure_github(body(('token','revision')))
        return jsonify(ok=True)
    return app
