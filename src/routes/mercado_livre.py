from flask import Blueprint, jsonify, request, redirect, session, url_for
import requests
import os
from urllib.parse import urlencode

mercado_livre_bp = Blueprint('mercado_livre', __name__)

# Configurações da aplicação Mercado Livre
CLIENT_ID = '7588002866610145'
CLIENT_SECRET = 'T9ueuIVjoLRjlJkfBQQwi4V8UqtebAWf'
REDIRECT_URI = 'http://localhost:5000/api/ml/callback'
AUTH_URL = 'https://auth.mercadolivre.com.br/authorization'
TOKEN_URL = 'https://api.mercadolivre.com/oauth/token'
API_BASE_URL = 'https://api.mercadolivre.com'

@mercado_livre_bp.route('/auth', methods=['GET'])
def auth():
    """Inicia o processo de autenticação OAuth"""
    params = {
        'response_type': 'code',
        'client_id': CLIENT_ID,
        'redirect_uri': REDIRECT_URI,
        'state': 'random_state_string'  # Em produção, use um valor aleatório seguro
    }
    
    auth_url = f"{AUTH_URL}?{urlencode(params)}"
    return jsonify({'auth_url': auth_url})

@mercado_livre_bp.route('/callback', methods=['GET'])
def callback():
    """Callback para receber o código de autorização"""
    code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')
    
    if error:
        return jsonify({'error': error}), 400
    
    if not code:
        return jsonify({'error': 'Código de autorização não recebido'}), 400
    
    # Trocar código por token
    token_data = {
        'grant_type': 'authorization_code',
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'code': code,
        'redirect_uri': REDIRECT_URI
    }
    
    try:
        response = requests.post(TOKEN_URL, data=token_data)
        response.raise_for_status()
        token_info = response.json()
        
        # Salvar token na sessão (em produção, use um banco de dados)
        session['access_token'] = token_info.get('access_token')
        session['refresh_token'] = token_info.get('refresh_token')
        session['user_id'] = token_info.get('user_id')
        session['expires_in'] = token_info.get('expires_in')
        
        return jsonify({
            'message': 'Autenticação realizada com sucesso!',
            'user_id': token_info.get('user_id'),
            'access_token': token_info.get('access_token')[:20] + '...'  # Mostrar apenas parte do token
        })
        
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Erro ao obter token: {str(e)}'}), 500

@mercado_livre_bp.route('/user-info', methods=['GET'])
def get_user_info():
    """Obter informações do usuário autenticado"""
    access_token = session.get('access_token')
    
    if not access_token:
        return jsonify({'error': 'Token de acesso não encontrado. Faça login primeiro.'}), 401
    
    headers = {'Authorization': f'Bearer {access_token}'}
    
    try:
        response = requests.get(f'{API_BASE_URL}/users/me', headers=headers)
        response.raise_for_status()
        user_info = response.json()
        
        return jsonify(user_info)
        
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Erro ao obter informações do usuário: {str(e)}'}), 500

@mercado_livre_bp.route('/my-items', methods=['GET'])
def get_my_items():
    """Obter todos os itens do usuário autenticado"""
    access_token = session.get('access_token')
    user_id = session.get('user_id')
    
    if not access_token or not user_id:
        return jsonify({'error': 'Token de acesso ou ID do usuário não encontrado. Faça login primeiro.'}), 401
    
    headers = {'Authorization': f'Bearer {access_token}'}
    
    # Parâmetros de paginação
    offset = request.args.get('offset', 0, type=int)
    limit = request.args.get('limit', 50, type=int)
    
    try:
        # Buscar itens do usuário
        params = {
            'offset': offset,
            'limit': limit
        }
        
        response = requests.get(f'{API_BASE_URL}/users/{user_id}/items/search', 
                              headers=headers, params=params)
        response.raise_for_status()
        items_data = response.json()
        
        # Obter detalhes de cada item
        detailed_items = []
        for item_id in items_data.get('results', []):
            try:
                item_response = requests.get(f'{API_BASE_URL}/items/{item_id}', headers=headers)
                item_response.raise_for_status()
                item_detail = item_response.json()
                
                # Extrair informações relevantes
                item_info = {
                    'id': item_detail.get('id'),
                    'title': item_detail.get('title'),
                    'price': item_detail.get('price'),
                    'currency_id': item_detail.get('currency_id'),
                    'available_quantity': item_detail.get('available_quantity'),
                    'sold_quantity': item_detail.get('sold_quantity'),
                    'condition': item_detail.get('condition'),
                    'listing_type_id': item_detail.get('listing_type_id'),
                    'status': item_detail.get('status'),
                    'permalink': item_detail.get('permalink'),
                    'thumbnail': item_detail.get('thumbnail'),
                    'category_id': item_detail.get('category_id'),
                    'date_created': item_detail.get('date_created'),
                    'last_updated': item_detail.get('last_updated')
                }
                detailed_items.append(item_info)
                
            except requests.exceptions.RequestException:
                # Se não conseguir obter detalhes de um item, pular
                continue
        
        return jsonify({
            'total': items_data.get('paging', {}).get('total', 0),
            'offset': offset,
            'limit': limit,
            'items': detailed_items
        })
        
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Erro ao obter itens: {str(e)}'}), 500

@mercado_livre_bp.route('/item/<item_id>', methods=['GET'])
def get_item_detail(item_id):
    """Obter detalhes completos de um item específico"""
    access_token = session.get('access_token')
    
    if not access_token:
        return jsonify({'error': 'Token de acesso não encontrado. Faça login primeiro.'}), 401
    
    headers = {'Authorization': f'Bearer {access_token}'}
    
    try:
        # Obter detalhes do item
        response = requests.get(f'{API_BASE_URL}/items/{item_id}', headers=headers)
        response.raise_for_status()
        item_detail = response.json()
        
        # Obter descrição do item
        try:
            desc_response = requests.get(f'{API_BASE_URL}/items/{item_id}/description', headers=headers)
            desc_response.raise_for_status()
            description = desc_response.json()
            item_detail['description'] = description
        except:
            item_detail['description'] = None
        
        return jsonify(item_detail)
        
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Erro ao obter detalhes do item: {str(e)}'}), 500

@mercado_livre_bp.route('/search', methods=['GET'])
def search_items():
    """Buscar itens por vendedor ou outros critérios"""
    access_token = session.get('access_token')
    
    if not access_token:
        return jsonify({'error': 'Token de acesso não encontrado. Faça login primeiro.'}), 401
    
    headers = {'Authorization': f'Bearer {access_token}'}
    
    # Parâmetros de busca
    seller_id = request.args.get('seller_id')
    nickname = request.args.get('nickname')
    category = request.args.get('category')
    q = request.args.get('q')  # termo de busca
    sort = request.args.get('sort', 'relevance')
    offset = request.args.get('offset', 0, type=int)
    limit = request.args.get('limit', 50, type=int)
    
    params = {
        'offset': offset,
        'limit': limit,
        'sort': sort
    }
    
    if seller_id:
        params['seller_id'] = seller_id
    if nickname:
        params['nickname'] = nickname
    if category:
        params['category'] = category
    if q:
        params['q'] = q
    
    try:
        response = requests.get(f'{API_BASE_URL}/sites/MLB/search', 
                              headers=headers, params=params)
        response.raise_for_status()
        search_results = response.json()
        
        return jsonify(search_results)
        
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Erro na busca: {str(e)}'}), 500

@mercado_livre_bp.route('/logout', methods=['POST'])
def logout():
    """Fazer logout (limpar sessão)"""
    session.clear()
    return jsonify({'message': 'Logout realizado com sucesso!'})

@mercado_livre_bp.route('/status', methods=['GET'])
def status():
    """Verificar status da autenticação"""
    access_token = session.get('access_token')
    user_id = session.get('user_id')
    
    if access_token and user_id:
        return jsonify({
            'authenticated': True,
            'user_id': user_id,
            'token_preview': access_token[:20] + '...' if access_token else None
        })
    else:
        return jsonify({'authenticated': False})

