from flask import Blueprint, request, jsonify, current_app
from config import Config
from utils.auth_middleware import token_required
import requests as http_requests

settings_bp = Blueprint('settings', __name__)

DEFAULT_APP_SETTINGS = {
    'gemini_api_key': '',
    'gemini_model': 'gemini-2.0-flash',
    'translate_prompt_en_to_vi': (
        'Translate the following English text to Vietnamese. Keep technical terms as-is. '
        'Only return the translated text, nothing else.\n\nText: {{text}}'
    ),
    'translate_prompt_vi_to_en': (
        'Translate the following Vietnamese text to English. Keep technical terms as-is. '
        'Only return the translated text, nothing else.\n\nText: {{text}}'
    ),
    'gemini_combine_prompt': (
        'Combine the following captions into a single, coherent description. '
        'Only return the combined text, nothing else.\n\nCaptions: {{captions}}'
    ),
    'timezone': 'Asia/Ho_Chi_Minh',
}


def _get_setting_value(key: str, default=''):
    try:
        doc = current_app.db.settings.find_one({'key': key})
        if doc is not None:
            return doc.get('value', default)
    except Exception:
        pass
    return default


def _set_setting_value(key: str, value):
    current_app.db.settings.update_one(
        {'key': key},
        {'$set': {'key': key, 'value': value}},
        upsert=True
    )


def get_dam_url():
    """Get DAM server URL from DB settings, fallback to Config."""
    try:
        doc = current_app.db.settings.find_one({'key': 'dam_server_url'})
        if doc and doc.get('value'):
            return doc['value'].rstrip('/')
    except Exception:
        pass
    return Config.DAM_SERVER_URL.rstrip('/')


@settings_bp.route('', methods=['GET'])
@token_required
def get_all_settings():
    """Get all app settings persisted on server."""
    return jsonify({
        'gemini_api_key': _get_setting_value('gemini_api_key', DEFAULT_APP_SETTINGS['gemini_api_key']),
        'gemini_model': _get_setting_value('gemini_model', DEFAULT_APP_SETTINGS['gemini_model']),
        'translate_prompt_en_to_vi': _get_setting_value(
            'translate_prompt_en_to_vi', DEFAULT_APP_SETTINGS['translate_prompt_en_to_vi']
        ),
        'translate_prompt_vi_to_en': _get_setting_value(
            'translate_prompt_vi_to_en', DEFAULT_APP_SETTINGS['translate_prompt_vi_to_en']
        ),
        'gemini_combine_prompt': _get_setting_value(
            'gemini_combine_prompt', DEFAULT_APP_SETTINGS['gemini_combine_prompt']
        ),
        'timezone': _get_setting_value('timezone', DEFAULT_APP_SETTINGS['timezone']),
        'dam_server_url': get_dam_url(),
    })


@settings_bp.route('', methods=['PUT'])
@token_required
def set_all_settings():
    """Persist all app settings on server."""
    data = request.get_json() or {}

    gemini_api_key = (data.get('gemini_api_key') or '').strip()
    gemini_model = (data.get('gemini_model') or DEFAULT_APP_SETTINGS['gemini_model']).strip()
    translate_prompt_en_to_vi = (
        data.get('translate_prompt_en_to_vi') or DEFAULT_APP_SETTINGS['translate_prompt_en_to_vi']
    )
    translate_prompt_vi_to_en = (
        data.get('translate_prompt_vi_to_en') or DEFAULT_APP_SETTINGS['translate_prompt_vi_to_en']
    )
    gemini_combine_prompt = (
        data.get('gemini_combine_prompt') or DEFAULT_APP_SETTINGS['gemini_combine_prompt']
    )
    timezone = (data.get('timezone') or DEFAULT_APP_SETTINGS['timezone']).strip()
    dam_server_url = (data.get('dam_server_url') or get_dam_url()).strip().rstrip('/')

    _set_setting_value('gemini_api_key', gemini_api_key)
    _set_setting_value('gemini_model', gemini_model)
    _set_setting_value('translate_prompt_en_to_vi', translate_prompt_en_to_vi)
    _set_setting_value('translate_prompt_vi_to_en', translate_prompt_vi_to_en)
    _set_setting_value('gemini_combine_prompt', gemini_combine_prompt)
    _set_setting_value('timezone', timezone)
    _set_setting_value('dam_server_url', dam_server_url)

    return jsonify({
        'gemini_api_key': gemini_api_key,
        'gemini_model': gemini_model,
        'translate_prompt_en_to_vi': translate_prompt_en_to_vi,
        'translate_prompt_vi_to_en': translate_prompt_vi_to_en,
        'gemini_combine_prompt': gemini_combine_prompt,
        'timezone': timezone,
        'dam_server_url': dam_server_url,
        'message': 'Settings updated'
    })


@settings_bp.route('/gemini', methods=['GET'])
@token_required
def get_gemini_settings():
    """Get persisted Gemini settings."""
    return jsonify({
        'gemini_api_key': _get_setting_value('gemini_api_key', ''),
        'gemini_model': _get_setting_value('gemini_model', 'gemini-2.0-flash'),
    })


@settings_bp.route('/gemini', methods=['PUT'])
@token_required
def set_gemini_settings():
    """Persist Gemini API key/model settings."""
    data = request.get_json() or {}
    gemini_api_key = (data.get('gemini_api_key') or '').strip()
    gemini_model = (data.get('gemini_model') or 'gemini-2.0-flash').strip()

    current_app.db.settings.update_one(
        {'key': 'gemini_api_key'},
        {'$set': {'key': 'gemini_api_key', 'value': gemini_api_key}},
        upsert=True
    )
    current_app.db.settings.update_one(
        {'key': 'gemini_model'},
        {'$set': {'key': 'gemini_model', 'value': gemini_model}},
        upsert=True
    )

    return jsonify({
        'gemini_api_key': gemini_api_key,
        'gemini_model': gemini_model,
        'message': 'Gemini settings updated'
    })


@settings_bp.route('/dam-url', methods=['GET'])
@token_required
def get_dam_server_url():
    """Get current DAM server URL"""
    url = get_dam_url()
    return jsonify({'dam_server_url': url})


@settings_bp.route('/dam-url', methods=['PUT'])
@token_required
def set_dam_server_url():
    """Update DAM server URL"""
    data = request.get_json()
    url = data.get('dam_server_url', '').strip().rstrip('/')

    if not url:
        return jsonify({'error': 'URL is required'}), 400

    current_app.db.settings.update_one(
        {'key': 'dam_server_url'},
        {'$set': {'key': 'dam_server_url', 'value': url}},
        upsert=True
    )

    return jsonify({'dam_server_url': url, 'message': 'DAM server URL updated'})


@settings_bp.route('/dam-url/test', methods=['POST'])
@token_required
def test_dam_connection():
    """Test connection to DAM server"""
    data = request.get_json()
    url = (data.get('dam_server_url') or get_dam_url()).strip().rstrip('/')

    try:
        resp = http_requests.get(f"{url}/health", timeout=5)
        if resp.status_code == 200:
            return jsonify({'status': 'ok', 'message': f'Connected to {url}', 'details': resp.json()})
        else:
            return jsonify({'status': 'error', 'message': f'Server responded with status {resp.status_code}'}), 502
    except http_requests.exceptions.ConnectionError:
        return jsonify({'status': 'error', 'message': f'Cannot connect to {url}'}), 502
    except http_requests.exceptions.Timeout:
        return jsonify({'status': 'error', 'message': f'Connection timed out to {url}'}), 504
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
