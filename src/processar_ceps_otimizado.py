"""
Script otimizado para processar CEPs únicos e obter coordenadas
"""
import pandas as pd
import numpy as np
from pathlib import Path
import requests
import time
import json
import pickle
from collections import defaultdict


def get_coordinates_from_cep_cached(cep, cache):
    """
    Obtém coordenadas de um CEP usando cache para evitar reprocessamento
    """
    if cep in cache:
        return cache[cep]
    
    # Limpa o CEP
    cep = str(cep).replace("-", "").replace(".", "")
    
    # Tenta usar a API ViaCEP primeiro
    try:
        url = f"https://viacep.com.br/ws/{cep}/json/"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if 'erro' not in data and data.get('logradouro'):
                # Monta endereço completo
                address_parts = []
                if data.get('logradouro'):
                    address_parts.append(data['logradouro'])
                if data.get('bairro'):
                    address_parts.append(data['bairro'])
                if data.get('localidade'):
                    address_parts.append(data['localidade'])
                if data.get('uf'):
                    address_parts.append(data['uf'])
                
                address = ", ".join(address_parts)
                
                # Usa Nominatim para geocodificar
                lat, lon = geocode_with_nominatim_cached(address, cep, cache)
                
                if lat and lon:
                    result = {'lat': lat, 'lon': lon, 'source': 'viacep+nominatim'}
                    cache[cep] = result
                    return result
    except Exception as e:
        print(f"Erro ViaCEP para CEP {cep}: {e}")
    
    # Se falhar, tenta CEP genérico (somente cidade)
    try:
        address = f"Teresina, PI, Brasil, CEP {cep}"
        lat, lon = geocode_with_nominatim_cached(address, cep, cache)
        
        if lat and lon:
            result = {'lat': lat, 'lon': lon, 'source': 'nominatim_fallback'}
            cache[cep] = result
            return result
    except:
        pass
    
    # Cache negativo para não tentar novamente
    cache[cep] = None
    return None


def geocode_with_nominatim_cached(address, cep, cache):
    """
    Geocodifica endereço usando Nominatim com cache
    """
    cache_key = f"addr_{hash(address)}"
    if cache_key in cache:
        return cache[cache_key]['lat'], cache[cache_key]['lon']
    
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            'q': address,
            'format': 'json',
            'limit': 1
        }
        headers = {'User-Agent': 'mapa-emprego-teresina/1.0'}
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data:
                lat = float(data[0]['lat'])
                lon = float(data[0]['lon'])
                
                # Cache o resultado do endereço
                cache[cache_key] = {'lat': lat, 'lon': lon}
                return lat, lon
    except Exception as e:
        print(f"Erro Nominatim para '{address}': {e}")
    
    return None, None


def create_fallback_coordinates():
    """
    Cria coordenadas de fallback para Teresina (centro e bairros principais)
    """
    # Coordenadas aproximadas para áreas de Teresina (baseadas em faixas de CEP)
    fallback_ranges = [
        # Centro (CEPs iniciados com 6400, 6401)
        {'prefix': '6400', 'lat': -5.0892, 'lon': -42.8019, 'area': 'Centro'},
        {'prefix': '6401', 'lat': -5.0979, 'lon': -42.7971, 'area': 'Centro'},
        
        # Zona Sul (CEPs iniciados com 6402, 6403)
        {'prefix': '6402', 'lat': -5.1214, 'lon': -42.7922, 'area': 'Zona Sul'},
        {'prefix': '6403', 'lat': -5.1345, 'lon': -42.7845, 'area': 'Zona Sul'},
        
        # Zona Leste (CEPs iniciados com 6404, 6405)
        {'prefix': '6404', 'lat': -5.0781, 'lon': -42.7842, 'area': 'Zona Leste'},
        {'prefix': '6405', 'lat': -5.0647, 'lon': -42.7648, 'area': 'Zona Leste'},
        
        # Zona Norte (CEPs iniciados com 6406, 6407)
        {'prefix': '6406', 'lat': -5.0464, 'lon': -42.7514, 'area': 'Zona Norte'},
        {'prefix': '6407', 'lat': -5.1177, 'lon': -42.7548, 'area': 'Zona Norte'},
        
        # Áreas mais afastadas (CEPs iniciados com 6408, 6409)
        {'prefix': '6408', 'lat': -5.1795, 'lon': -42.7580, 'area': 'Áreas Periféricas'},
        {'prefix': '6409', 'lat': -5.1890, 'lon': -42.7399, 'area': 'Áreas Periféricas'},
    ]
    
    return fallback_ranges


def get_fallback_coordinate(cep, fallback_ranges):
    """
    Obtém coordenada de fallback baseada no prefixo do CEP
    """
    cep_prefix = str(cep)[:4]
    
    for range_data in fallback_ranges:
        if cep_prefix == range_data['prefix']:
            return {
                'lat': range_data['lat'], 
                'lon': range_data['lon'], 
                'source': 'fallback_by_prefix'
            }
    
    # Fallback geral para Teresina
    return {'lat': -5.0892, 'lon': -42.8019, 'source': 'fallback_geral'}


def load_cache(cache_file):
    """
    Carrega cache de coordenadas se existir
    """
    if cache_file.exists():
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {}


def save_cache(cache, cache_file):
    """
    Salva cache de coordenadas
    """
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def process_csv_with_coordinates_optimized(input_csv, output_csv):
    """
    Processa CSV e adiciona coordenadas de forma otimizada
    """
    print(f"Lendo CSV: {input_csv}")
    df = pd.read_csv(input_csv)
    
    print(f"Total de registros: {len(df)}")
    print(f"CEPs únicos: {df['cep'].nunique()}")
    
    # Carrega cache se existir
    cache_file = input_csv.parent / "cep_coordinates_cache.json"
    cache = load_cache(cache_file)
    print(f"Cache carregado: {len(cache)} coordenadas")
    
    # Obtém CEPs únicos
    unique_ceps = df['cep'].unique()
    print(f"Processando {len(unique_ceps)} CEPs únicos...")
    
    # Fallback ranges
    fallback_ranges = create_fallback_coordinates()
    
    # Processa CEPs únicos
    processed = 0
    failed = 0
    
    for cep in unique_ceps:
        if pd.notna(cep):
            # Verifica se já está no cache
            if str(cep) in cache:
                processed += 1
                continue
            
            # Tenta geocodificar
            coord_data = get_coordinates_from_cep_cached(cep, cache)
            
            if coord_data and coord_data.get('lat') and coord_data.get('lon'):
                processed += 1
                print(f"✓ CEP {cep}: {coord_data['lat']:.4f}, {coord_data['lon']:.4f} ({coord_data['source']})")
            else:
                # Usa fallback
                fallback_coord = get_fallback_coordinate(cep, fallback_ranges)
                cache[str(cep)] = fallback_coord
                failed += 1
                print(f"⚠ CEP {cep}: usando fallback - {fallback_coord['lat']:.4f}, {fallback_coord['lon']:.4f}")
            
            # Pausa para não sobrecarregar a API (a cada 5 CEPs)
            if (processed + failed) % 5 == 0:
                time.sleep(0.5)
            
            # Salva cache a cada 50 CEPs
            if (processed + failed) % 50 == 0:
                save_cache(cache, cache_file)
                print(f"Cache salvo. Progresso: {processed + failed}/{len(unique_ceps)}")
    
    # Salva cache final
    save_cache(cache, cache_file)
    
    # Atribui coordenadas aos dados originais
    print("Atribuindo coordenadas aos dados...")
    df['latitude'] = None
    df['longitude'] = None
    df['coord_source'] = None
    
    for idx, row in df.iterrows():
        cep = str(row['cep'])
        if cep in cache and cache[cep]:
            df.at[idx, 'latitude'] = cache[cep]['lat']
            df.at[idx, 'longitude'] = cache[cep]['lon']
            df.at[idx, 'coord_source'] = cache[cep]['source']
    
    # Estatísticas
    geocodificados = df['latitude'].notna().sum()
    print(f"\nResumo:")
    print(f"Total de registros: {len(df)}")
    print(f"CEPs únicos processados: {len(unique_ceps)}")
    print(f"Registros com coordenadas: {geocodificados}/{len(df)} ({geocodificados/len(df)*100:.1f}%)")
    print(f"CEPs geocodificados via API: {processed - failed}")
    print(f"CEPs usando fallback: {failed}")
    
    # Salva resultado
    df.to_csv(output_csv, index=False)
    print(f"\nResultado salvo em: {output_csv}")
    
    # Salva também o mapeamento de CEPs
    mapping_file = output_csv.parent / "cep_coordenadas_mapping.json"
    # Remove entradas None do cache
    clean_cache = {k: v for k, v in cache.items() if v is not None}
    with open(mapping_file, 'w', encoding='utf-8') as f:
        json.dump(clean_cache, f, ensure_ascii=False, indent=2)
    print(f"Mapeamento de CEPs salvo em: {mapping_file}")
    
    return df


if __name__ == "__main__":
    # Caminhos
    repo_root = Path(__file__).resolve().parents[1]
    input_csv = repo_root / "data" / "empregos_rais.csv"
    output_csv = repo_root / "data" / "ceps_com_coordenadas_otimizado.csv"
    
    if input_csv.exists():
        process_csv_with_coordinates_optimized(input_csv, output_csv)
    else:
        print(f"Arquivo não encontrado: {input_csv}")
        print("Criando dados de exemplo...")
        # sample_path = create_sample_data()
        # process_csv_with_coordinates_optimized(sample_path, output_csv)