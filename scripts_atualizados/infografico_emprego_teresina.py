#!/usr/bin/env python3
"""
Infográfico de Emprego Formal por Bairro - Teresina/PI
====================================================

Este script gera mapas de emprego formal por bairro em Teresina usando:
- Dados da RAIS (Relação Anual de Informações Sociais)
- Shapefile de bairros de Teresina
- Geocodificação de CEPs para coordenadas precisas

Autor: Sistema de Análise de Dados
Data: 2025
"""

import json
import warnings
from pathlib import Path

import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from shapely.geometry import Point

# Configurações principais
CONFIG = {
    "municipio_ibge": "2211001",  # Código IBGE de Teresina
    "anos_analise": [2004, 2023],
    "escala_pontos": 1000,  # 1 ponto = 1000 vínculos
    "cores": {
        "fundo": "#f8f8f8",
        "pontos": "#1f77b4",
        "bordas": "darkgray",
        "labels": "white"
    },
    "labels_destaque": {
        2004: ["CENTRO", "DIRCEU ARCOVERDE"],
        2023: ["FATIMA", "DIRCEU ARCOVERDE"]
    }
}

# Suprimir warnings
warnings.filterwarnings("ignore")


class ProcessadorRAIS:
    """Classe principal para processar dados da RAIS e gerar mapas"""
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.shapefile_path = data_dir / "BAIRROS_2013.shp"
        self.dados_path = data_dir / "ceps_com_coordenadas_otimizado.csv"
        self.mapping_path = data_dir / "cep_coordenadas_mapping.json"
        
    def carregar_dados(self) -> tuple[pd.DataFrame, gpd.GeoDataFrame]:
        """Carrega dados RAIS e shapefile"""
        print("📊 Carregando dados...")
        
        # Carrega dados RAIS com coordenadas
        df = pd.read_csv(self.dados_path)
        print(f"   ✓ Dados RAIS: {len(df):,} registros")
        
        # Carrega shapefile
        shp = gpd.read_file(self.shapefile_path)
        print(f"   ✓ Shapefile: {len(shp)} bairros")
        
        # Padroniza nomes de bairros
        shp = self._padronizar_bairros(shp)
        
        return df, shp
    
    def _padronizar_bairros(self, shp: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """Padroniza nomes de bairros do shapefile"""
        # Encontra coluna de bairros
        col_bairro = None
        for col in shp.columns:
            if any(term in col.upper() for term in ['BAIRRO', 'NOME', 'NM_']):
                col_bairro = col
                break
        
        if col_bairro is None:
            raise ValueError("Coluna de bairro não encontrada no shapefile")
        
        # Padroniza nomes
        shp = shp[[col_bairro, 'geometry']].copy()
        shp.columns = ['bairro', 'geometry']
        shp['bairro'] = shp['bairro'].astype(str).str.strip().str.upper()
        
        return shp
    
    def atribuir_bairros(self, df: pd.DataFrame, shp: gpd.GeoDataFrame) -> pd.DataFrame:
        """Atribui cada CEP ao seu bairro correspondente"""
        print("\n🗺️  Atribuindo CEPs aos bairros...")
        
        # Cria pontos geográficos em WGS84 (coordenadas dos CEPs)
        geometry = [Point(lon, lat) for lon, lat in zip(df['longitude'], df['latitude'])]
        pontos_gdf = gpd.GeoDataFrame(df, geometry=geometry, crs='EPSG:4326')
        
        # Transforma para o CRS do shapefile (EPSG:31983)
        pontos_gdf = pontos_gdf.to_crs(shp.crs)
        
        # Faz spatial join
        resultado = gpd.sjoin(pontos_gdf, shp, how='left', predicate='within')
        
        # Estatísticas
        atribuidos = resultado['bairro'].notna().sum()
        total = len(resultado)
        print(f"   ✓ CEPs atribuídos: {atribuidos:,}/{total:,} ({atribuidos/total*100:.1f}%)")
        
        # Remove sem bairro
        resultado = resultado.dropna(subset=['bairro'])
        resultado = resultado.rename(columns={'bairro': 'bairro_nome'})
        
        return resultado
    
    def agregar_dados(self, df: pd.DataFrame) -> pd.DataFrame:
        """Agrega dados por bairro e ano"""
        print("\n📈 Agregando dados...")
        
        resultado = df.groupby(['bairro_nome', 'ano']).agg({
            'quantidade_vinculos_ativos': 'sum',
            'latitude': 'mean',
            'longitude': 'mean'
        }).reset_index()
        
        # Calcula percentuais
        total_ano = resultado.groupby('ano')['quantidade_vinculos_ativos'].transform('sum')
        resultado['percentual'] = resultado['quantidade_vinculos_ativos'] / total_ano * 100
        
        print(f"   ✓ Total de vínculos: {resultado['quantidade_vinculos_ativos'].sum():,}")
        
        return resultado
    
    def criar_pontos_visualizacao(self, df_agg: pd.DataFrame, shp: gpd.GeoDataFrame, ano: int) -> gpd.GeoDataFrame:
        """Cria pontos de visualização para o mapa"""
        dados_ano = df_agg[df_agg['ano'] == ano].copy()
        
        pontos = []
        for _, row in dados_ano.iterrows():
            vinculos = row['quantidade_vinculos_ativos']
            if vinculos > 0:
                # Calcula número de pontos (1 ponto a cada 1000 vínculos)
                num_pontos = int(round(vinculos / CONFIG["escala_pontos"]))
                
                # Adiciona pequena variação aleatória
                import random
                for _ in range(num_pontos):
                    lat_var = row['latitude'] + random.uniform(-0.0005, 0.0005)
                    lon_var = row['longitude'] + random.uniform(-0.0005, 0.0005)
                    pontos.append({
                        'bairro': row['bairro_nome'],
                        'geometry': Point(lon_var, lat_var)
                    })
        
        if pontos:
            return gpd.GeoDataFrame(pontos, crs=shp.crs)
        else:
            return gpd.GeoDataFrame(geometry=[], crs=shp.crs)
    
    def gerar_mapa(self, df_agg: pd.DataFrame, shp: gpd.GeoDataFrame, ano: int, output_path: Path):
        """Gera mapa para um ano específico"""
        print(f"\n🗺️  Gerando mapa para {ano}...")
        
        # Prepara dados
        dados_mapa = shp.merge(
            df_agg[df_agg['ano'] == ano][['bairro_nome', 'quantidade_vinculos_ativos', 'percentual']],
            left_on='bairro', right_on='bairro_nome', how='left'
        )
        dados_mapa['quantidade_vinculos_ativos'] = dados_mapa['quantidade_vinculos_ativos'].fillna(0)
        
        # Cria pontos de visualização
        pontos_gdf = self.criar_pontos_visualizacao(df_agg, shp, ano)
        
        # Cria figura
        fig, ax = plt.subplots(figsize=(10, 8), dpi=300)
        
        # Fundo
        ax.set_facecolor(CONFIG["cores"]["fundo"])
        fig.patch.set_facecolor(CONFIG["cores"]["fundo"])
        
        # Plota bairros
        dados_mapa.boundary.plot(ax=ax, color=CONFIG["cores"]["bordas"], linewidth=0.5, alpha=0.7)
        
        # Plota pontos
        if len(pontos_gdf) > 0:
            pontos_gdf.plot(ax=ax, color=CONFIG["cores"]["pontos"], markersize=2, alpha=0.8)
        
        # Adiciona labels de bairros destacados
        bairros_destaque = CONFIG["labels_destaque"].get(ano, [])
        if bairros_destaque:
            for bairro in bairros_destaque:
                bairro_data = dados_mapa[dados_mapa['bairro'] == bairro]
                if not bairro_data.empty:
                    centroid = bairro_data.geometry.centroid.iloc[0]
                    ax.text(
                        centroid.x, centroid.y,
                        bairro.title(),
                        fontsize=8,
                        ha='center',
                        va='center',
                        bbox=dict(boxstyle='round,pad=0.3', 
                                facecolor=CONFIG["cores"]["labels"], 
                                alpha=0.8,
                                edgecolor='none')
                    )
        
        # Configurações
        ax.set_axis_off()
        ax.set_aspect('equal')
        ax.set_title(f'Emprego Formal por Bairro - Teresina/{ano}', 
                    fontsize=14, fontweight='bold', pad=20)
        
        # Legenda
        legenda_text = f'Cada ponto = {CONFIG["escala_pontos"]:,} vínculos\nTotal: {dados_mapa["quantidade_vinculos_ativos"].sum():,}'
        ax.text(0.02, 0.98, legenda_text, 
                transform=ax.transAxes,
                fontsize=8,
                verticalalignment='top',
                bbox=dict(boxstyle='round,pad=0.5', 
                         facecolor='white', 
                         alpha=0.9,
                         edgecolor='gray'))
        
        # Salva
        plt.tight_layout()
        fig.savefig(output_path, dpi=300, bbox_inches='tight', 
                   facecolor=CONFIG["cores"]["fundo"])
        plt.close()
        
        print(f"   ✓ Mapa salvo: {output_path.name}")
    
    def gerar_relatorio(self, df_agg: pd.DataFrame, output_path: Path):
        """Gera relatório estatístico"""
        print("\n📊 Gerando relatório...")
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("RELATÓRIO DE EMPREGO FORMAL - TERESINA/PI\n")
            f.write("=" * 50 + "\n\n")
            
            for ano in sorted(df_agg['ano'].unique()):
                dados_ano = df_agg[df_agg['ano'] == ano]
                
                f.write(f"ANO {ano}:\n")
                f.write("-" * 20 + "\n")
                f.write(f"Total de vínculos: {dados_ano['quantidade_vinculos_ativos'].sum():,}\n")
                f.write(f"Número de bairros: {len(dados_ano)}\n")
                f.write(f"Média por bairro: {dados_ano['quantidade_vinculos_ativos'].mean():.0f}\n\n")
                
                # Top 5 bairros
                top5 = dados_ano.nlargest(5, 'quantidade_vinculos_ativos')
                f.write("Top 5 bairros:\n")
                for i, (_, row) in enumerate(top5.iterrows(), 1):
                    f.write(f"  {i}. {row['bairro_nome'].title()}: {row['quantidade_vinculos_ativos']:,} ({row['percentual']:.1f}%)\n")
                f.write("\n")
        
        print(f"   ✓ Relatório salvo: {output_path.name}")
    
    def executar(self):
        """Executa o processamento completo"""
        print("🚀 Iniciando processamento de dados RAIS...")
        print("=" * 50)
        
        # Carrega dados
        df, shp = self.carregar_dados()
        
        # Atribui bairros
        df_com_bairros = self.atribuir_bairros(df, shp)
        
        # Agrega dados
        df_agg = self.agregar_dados(df_com_bairros)
        
        # Gera mapas para cada ano
        output_dir = self.data_dir.parent / "output"
        output_dir.mkdir(exist_ok=True)
        
        for ano in CONFIG["anos_analise"]:
            mapa_path = output_dir / f"mapa_emprego_teresina_{ano}.png"
            self.gerar_mapa(df_agg, shp, ano, mapa_path)
        
        # Gera relatório
        relatorio_path = output_dir / "relatorio_emprego_teresina.txt"
        self.gerar_relatorio(df_agg, relatorio_path)
        
        print("\n" + "=" * 50)
        print("✅ Processamento concluído com sucesso!")
        print(f"📁 Arquivos salvos em: {output_dir}")


def main():
    """Função principal"""
    # Diretório de dados
    data_dir = Path(__file__).parent / "data"
    
    # Verifica se arquivos existem
    arquivos_necessarios = [
        data_dir / "BAIRROS_2013.shp",
        data_dir / "ceps_com_coordenadas_otimizado.csv"
    ]
    
    for arquivo in arquivos_necessarios:
        if not arquivo.exists():
            print(f"❌ Arquivo não encontrado: {arquivo}")
            return
    
    # Executa processamento
    processador = ProcessadorRAIS(data_dir)
    processador.executar()


if __name__ == "__main__":
    main()