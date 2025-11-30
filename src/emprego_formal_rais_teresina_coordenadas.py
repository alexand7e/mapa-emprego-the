"""
Infográfico de emprego formal (RAIS) por bairro em Teresina
Versão com geocodificação de CEPs

Este script recria o projeto "emprego_formal_rais" em Python, mas agora usa coordenadas reais dos CEPs
"""
from pathlib import Path
import os
import math
import random
import warnings

import numpy as np
import pandas as pd

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

import geopandas as gpd
from shapely.geometry import Point


MAIN_CONFIG = {
    "municipio_ibge": "2211001",
    "anos": [2004, 2023],
    "bairro_col_candidates": [
        "nomebairro",
        "BAIRRO",
        "BAIRROS",
        "NOME",
        "NM_BAIRRO",
        "Nome_Bairro",
    ],
    "label_bairros_ano": {
        2004: ["Centro", "Dirceu Arcoverde"],
        2023: ["Fátima", "Dirceu Arcoverde"],
    },
    "bg_color": "#f8f8f8",
    "dot_color": "#1f77b4",
}

CACHE_CSV_PATH = Path(__file__).parent / "rais_dados_coordenadas.csv"


def read_bairros_shp(shp_path: Path) -> gpd.GeoDataFrame:
    """
    Lê shapefile de bairros e padroniza nomes
    """
    gdf = gpd.read_file(shp_path)
    
    # Encontra coluna de bairro
    bairro_col = None
    for cand in MAIN_CONFIG["bairro_col_candidates"]:
        if cand in gdf.columns:
            bairro_col = cand
            break
    if bairro_col is None:
        raise ValueError(f"Coluna de bairro não encontrada. Colunas disponíveis: {list(gdf.columns)}")
    
    # Renomeia e limpa
    gdf = gdf[[bairro_col, "geometry"]].copy()
    gdf.columns = ["bairro", "geometry"]
    
    # Padroniza nomes de bairros
    gdf["bairro"] = (
        gdf["bairro"]
        .astype(str)
        .str.strip()
        .str.upper()
        .str.normalize("NFKD")
        .str.encode("ascii", "ignore")
        .str.decode("ascii")
    )
    return gdf


def process_data_with_coordinates(csv_path: Path) -> pd.DataFrame:
    """
    Processa CSV com CEPs e coordenadas
    """
    df = pd.read_csv(csv_path)
    
    # Verifica colunas necessárias
    required_cols = ['cep', 'quantidade_vinculos_ativos', 'ano']
    if not all(col in df.columns for col in required_cols):
        raise ValueError(f"CSV deve conter colunas: {required_cols}")
    
    # Se tiver coordenadas, usa elas
    if 'latitude' in df.columns and 'longitude' in df.columns:
        print("Usando coordenadas do CSV")
        return df
    
    # Se não tiver, tenta geocodificar
    print("Geocodificando CEPs...")
    from cep_geocoder import process_ceps_with_coordinates
    
    output_path = csv_path.parent / "ceps_com_coordenadas.csv"
    df_coord = process_ceps_with_coordinates(csv_path, output_path)
    return df_coord


def assign_points_to_bairros(df: pd.DataFrame, shp_gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    """
    Atribui cada ponto (CEP) ao bairro correspondente no shapefile
    """
    # Cria GeoDataFrame com pontos
    geometry = [Point(xy) for xy in zip(df['longitude'], df['latitude'])]
    points_gdf = gpd.GeoDataFrame(df, geometry=geometry, crs=shp_gdf.crs)
    
    # Faz spatial join para atribuir bairros
    joined = gpd.sjoin(points_gdf, shp_gdf, how='left', predicate='within')
    
    # Remove pontos fora de qualquer bairro
    pontos_fora = joined['bairro_right'].isna().sum()
    if pontos_fora > 0:
        print(f"Atenção: {pontos_fora} CEPs estão fora dos limites dos bairros no shapefile")
        joined = joined.dropna(subset=['bairro_right'])
    
    # Renomeia colunas
    joined = joined.rename(columns={'bairro_right': 'bairro'})
    joined['bairro'] = joined['bairro'].str.upper()
    
    return joined


def aggregate_by_bairro_ano(df: pd.DataFrame) -> pd.DataFrame:
    """
    Agrega dados por bairro e ano
    """
    result = df.groupby(['bairro', 'ano']).agg({
        'quantidade_vinculos_ativos': 'sum',
        'latitude': 'mean',  # Centroide dos CEPs do bairro
        'longitude': 'mean'
    }).reset_index()
    
    result.columns = ['bairro', 'ano', 'vinculos_ativos', 'lat_centroid', 'lon_centroid']
    return result


def compute_share(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula percentuais e prepara dados para visualização
    """
    df = df.copy()
    total = df.groupby("ano")["vinculos_ativos"].transform("sum")
    df["pct"] = df["vinculos_ativos"] / total * 100.0
    
    # Pivot para formato wide
    wide = df.pivot(index="bairro", columns="ano", values=["vinculos_ativos", "pct", "lat_centroid", "lon_centroid"])
    wide.columns = [f"{lvl0}_{lvl1}" for (lvl0, lvl1) in wide.columns]
    wide = wide.reset_index()
    return wide


def create_points_for_viz(data_wide: pd.DataFrame, shp_gdf: gpd.GeoDataFrame, ano: int) -> gpd.GeoDataFrame:
    """
    Cria pontos de visualização baseados nas coordenadas reais dos CEPs
    """
    points_data = []
    
    for _, row in data_wide.iterrows():
        bairro = row['bairro']
        vinculos = row[f'vinculos_ativos_{ano}']
        lat_centroid = row[f'lat_centroid_{ano}']
        lon_centroid = row[f'lon_centroid_{ano}']
        
        if pd.notna(vinculos) and vinculos > 0 and pd.notna(lat_centroid) and pd.notna(lon_centroid):
            # Cria 1 ponto a cada 1000 vínculos, posicionados próximo ao centroide
            num_points = int(round(vinculos / 1000.0))
            
            # Adiciona pequena variação aleatória ao redor do centroide
            for i in range(num_points):
                # Variação de ~100m ao redor do ponto central
                lat_var = lat_centroid + random.uniform(-0.001, 0.001)
                lon_var = lon_centroid + random.uniform(-0.001, 0.001)
                points_data.append({
                    'bairro': bairro,
                    'geometry': Point(lon_var, lat_var)
                })
    
    if points_data:
        points_gdf = gpd.GeoDataFrame(points_data, crs=shp_gdf.crs)
        return points_gdf
    else:
        return gpd.GeoDataFrame(geometry=[], crs=shp_gdf.crs)


def make_map_and_bars(shp_gdf: gpd.GeoDataFrame, data_wide: pd.DataFrame, ano: int, out_path: Path):
    """
    Cria mapa com pontos baseados em coordenadas reais dos CEPs
    """
    # Merge com dados do ano
    dados = shp_gdf.merge(
        data_wide[["bairro", f"vinculos_ativos_{ano}", f"pct_{ano}", f"lat_centroid_{ano}", f"lon_centroid_{ano}"]], 
        on="bairro", how="left"
    )
    dados[f"vinculos_ativos_{ano}"] = dados[f"vinculos_ativos_{ano}"].fillna(0)
    
    # Cria pontos de visualização com coordenadas reais
    pts_gdf = create_points_for_viz(data_wide, shp_gdf, ano)
    
    # Cria figura
    fig = plt.figure(figsize=(8, 6), dpi=400)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.add_patch(Rectangle((0, 0), 1, 1, transform=ax.transAxes, color=MAIN_CONFIG["bg_color"]))
    
    # Plota limites dos bairros
    dados.boundary.plot(ax=ax, color="darkgray", linewidth=0.3)
    
    # Plota pontos se houver
    if len(pts_gdf) > 0:
        pts_gdf.plot(ax=ax, color=MAIN_CONFIG["dot_color"], markersize=1)
    
    # Adiciona labels de bairros principais
    labels_sel = MAIN_CONFIG["label_bairros_ano"].get(ano, [])
    if labels_sel:
        sel_df = dados[dados["bairro"].isin([s.upper() for s in labels_sel])].copy()
        if not sel_df.empty:
            for _, row in sel_df.iterrows():
                if pd.notna(row[f"lat_centroid_{ano}"]) and pd.notna(row[f"lon_centroid_{ano}"]):
                    ax.text(
                        row[f"lon_centroid_{ano}"], 
                        row[f"lat_centroid_{ano}"],
                        row["bairro"].title(),
                        fontsize=6,
                        ha="center",
                        va="center",
                        bbox=dict(boxstyle="round,pad=0.2", facecolor="white", alpha=0.8, edgecolor="none")
                    )
    
    # Configurações do mapa
    ax.set_axis_off()
    ax.set_aspect('equal')
    
    # Salva figura
    fig.savefig(out_path, bbox_inches="tight", facecolor=MAIN_CONFIG["bg_color"], dpi=400)
    plt.close(fig)
    print(f"Mapa salvo: {out_path}")


def main():
    """
    Função principal
    """
    warnings.filterwarnings("ignore")
    
    # Paths
    repo_root = Path(__file__).resolve().parents[1]
    shp_path = repo_root / "BAIRROS_2013.shp"
    csv_path = repo_root / "bquxjob_4debdb75_19ad4877d50.csv"
    
    print("Lendo shapefile...")
    shp_gdf = read_bairros_shp(shp_path)
    
    print("Processando dados com CEPs...")
    df = process_data_with_coordinates(csv_path)
    
    print("Atribuindo CEPs aos bairros...")
    df_with_bairros = assign_points_to_bairros(df, shp_gdf)
    
    print("Agregando por bairro e ano...")
    df_agg = aggregate_by_bairro_ano(df_with_bairros)
    
    print("Calculando percentuais...")
    data_wide = compute_share(df_agg)
    
    print("Gerando mapas...")
    for ano in MAIN_CONFIG["anos"]:
        out = Path(__file__).resolve().parent / f"mapa_com_coordenadas_{ano}.png"
        make_map_and_bars(shp_gdf, data_wide, ano, out)
    
    print("Concluído!")


if __name__ == "__main__":
    main()