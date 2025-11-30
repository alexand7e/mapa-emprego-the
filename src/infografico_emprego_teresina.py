#!/usr/bin/env python3
"""
Infográfico de Emprego Formal por Bairro - Teresina/PI
====================================================

Este script gera mapas de emprego formal por bairro em Teresina usando:
- Dados da RAIS (Relação Anual de Informações Sociais)
- Shapefile de bairros de Teresina
- Geocodificação de CEPs para coordenadas precisas

Autor: Alexandre
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

# Configurações principais - Estilo dark theme inspirado no R
CONFIG = {
    "municipio_ibge": "2211001",  # Código IBGE de Teresina
    "anos_analise": [2023],
    "escala_pontos": 1000,  # 1 ponto = 1000 vínculos
    "cores": {
        "fundo": "#404044",      # Cinza escuro do R
        "fundo_claro": "#2a2a2e", # Fundo do gráfico
        "pontos": "#4ECDC4",     # Verde água do R
        "bordas": "#666666",     # Cinza médio para bordas
        "labels": "#effae6",     # Verde claro quase branco
        "texto": "#effae6",      # Texto branco
        "legenda": "#effae6"     # Texto da legenda
    },
    "labels_destaque": {
        # 2004: ["CENTRO", "DIRCEU ARCOVERDE"],
        2023: ["FATIMA", "DIRCEU ARCOVERDE"]
    },
    "fonte": {
        "titulo": 20,
        "subtitulo": 14,
        "legenda": 10,
        "label": 9
    },
    "dispersao": {
        "tamanho_min": 8,
        "tamanho_max": 90,
        "transparencia_min": 0.1,
        "transparencia_max": 0.88,
        "sobreposicao": "proporcional"
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
        print("Carregando dados...")
        
        # Carrega dados RAIS com coordenadas
        df = pd.read_csv(self.dados_path)
        print(f"   ✓ Dados RAIS: {len(df):,} registros")
        
        # Atualiza configuração com anos disponíveis
        anos_disponiveis = sorted(df['ano'].unique())
        global CONFIG
        CONFIG["anos_analise"] = anos_disponiveis
        print(f"   ✓ Anos disponíveis: {anos_disponiveis}")
        
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
        print("\n  Atribuindo CEPs aos bairros...")
        
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
        print("\n Agregando dados...")
        
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
    
    def calcular_tamanho_transparencia_pontos(self, vinculos: int, min_vinculos: int, max_vinculos: int) -> tuple[float, float]:
        """Calcula tamanho e transparência dos pontos proporcionalmente"""
        # Calcula tamanho proporcional
        if max_vinculos == min_vinculos:
            tamanho = CONFIG["dispersao"]["tamanho_max"]
            transparencia = CONFIG["dispersao"]["transparencia_max"]
        else:
            tamanho = (
                CONFIG["dispersao"]["tamanho_min"] + 
                (vinculos - min_vinculos) * 
                (CONFIG["dispersao"]["tamanho_max"] - CONFIG["dispersao"]["tamanho_min"]) / 
                (max_vinculos - min_vinculos)
            )
            boost = 1 + 0.15 * ((vinculos - min_vinculos) / (max_vinculos - min_vinculos))
            tamanho = min(CONFIG["dispersao"]["tamanho_max"], tamanho * boost)
            transparencia = (
                CONFIG["dispersao"]["transparencia_min"] + 
                (vinculos - min_vinculos) * 
                (CONFIG["dispersao"]["transparencia_max"] - CONFIG["dispersao"]["transparencia_min"]) / 
                (max_vinculos - min_vinculos)
            )
            transparencia = min(CONFIG["dispersao"]["transparencia_max"], transparencia)
        
        return tamanho, transparencia
    
    def criar_pontos_visualizacao_ceps(self, df: pd.DataFrame, shp: gpd.GeoDataFrame, ano: int) -> gpd.GeoDataFrame:
        """Cria pontos de visualização usando coordenadas reais dos CEPs com tamanho/transparência proporcional"""
        dados_ano = df[df['ano'] == ano].copy()
        
        # Calcula min/max de vínculos para normalização
        min_vinculos = dados_ano['quantidade_vinculos_ativos'].min()
        max_vinculos = dados_ano['quantidade_vinculos_ativos'].max()
        
        pontos = []
        for _, row in dados_ano.iterrows():
            vinculos = row['quantidade_vinculos_ativos']
            if vinculos > 0 and pd.notna(row['latitude']) and pd.notna(row['longitude']):
                # Calcula tamanho e transparência proporcionais
                tamanho, transparencia = self.calcular_tamanho_transparencia_pontos(
                    vinculos, min_vinculos, max_vinculos
                )
                
                # Reduz número de pontos para CEPs com muitos empregos (evita sobreposição excessiva)
                if vinculos >= 5000:  # CEPs com muitos empregos
                    num_pontos = max(1, int(round(vinculos / (CONFIG["escala_pontos"] * 2))))  # Metade dos pontos
                else:
                    num_pontos = max(1, int(round(vinculos / CONFIG["escala_pontos"])))
                
                # Adiciona pequena variação aleatória para não ficar tudo no mesmo ponto
                import random
                for _ in range(num_pontos):
                    # Usa coordenadas reais do CEP com pequena variação
                    lat_var = row['latitude'] + random.uniform(-0.00015, 0.00015)
                    lon_var = row['longitude'] + random.uniform(-0.00015, 0.00015)
                    
                    # Cria ponto em WGS84 e transforma para o CRS do shapefile
                    ponto_wgs84 = gpd.GeoDataFrame(
                        [{'geometry': Point(lon_var, lat_var)}], 
                        crs='EPSG:4326'
                    )
                    ponto_transformado = ponto_wgs84.to_crs(shp.crs)
                    
                    pontos.append({
                        'cep': row['cep'],
                        'bairro': row.get('bairro_nome', 'Desconhecido'),
                        'vinculos': vinculos,
                        'tamanho': tamanho,
                        'transparencia': transparencia,
                        'geometry': ponto_transformado.geometry.iloc[0]
                    })
        
        if pontos:
            return gpd.GeoDataFrame(pontos, crs=shp.crs)
        else:
            return gpd.GeoDataFrame(geometry=[], crs=shp.crs)
    
    def gerar_mapa_com_grafico(self, df: pd.DataFrame, df_agg: pd.DataFrame, shp: gpd.GeoDataFrame, ano: int, output_path: Path):
        """Gera mapa com gráfico de barras integrado no canto inferior esquerdo"""
        print(f"\n  Gerando mapa com gráfico para {ano}...")
        
        # Prepara dados do mapa
        dados_mapa = shp.merge(
            df_agg[df_agg['ano'] == ano][['bairro_nome', 'quantidade_vinculos_ativos', 'percentual']],
            left_on='bairro', right_on='bairro_nome', how='left'
        )
        dados_mapa['quantidade_vinculos_ativos'] = dados_mapa['quantidade_vinculos_ativos'].fillna(0)
        
        # Cria figura
        fig = plt.figure(figsize=(16, 12), dpi=300)
        ax_mapa = plt.axes([0.05, 0.05, 0.9, 0.9])
        ax_mapa.set_facecolor(CONFIG["cores"]["fundo_claro"])
        fig.patch.set_facecolor(CONFIG["cores"]["fundo"])

        # Plota bairros
        dados_mapa.boundary.plot(ax=ax_mapa, color=CONFIG["cores"]["bordas"], linewidth=0.6, alpha=0.9, zorder=1)

        # Ajusta limites e aspecto
        minx, miny, maxx, maxy = dados_mapa.total_bounds
        dx = (maxx - minx) * 0.02
        dy = (maxy - miny) * 0.02
        ax_mapa.set_xlim(minx - dx, maxx + dx)
        ax_mapa.set_ylim(miny - dy, maxy + dy)
        ax_mapa.set_aspect('equal')
        ax_mapa.set_xticks([])
        ax_mapa.set_yticks([])
        for spine in ax_mapa.spines.values():
            spine.set_visible(False)
        
        # Cria pontos de visualização
        pontos_gdf = self.criar_pontos_visualizacao_ceps(df, shp, ano)

        # Plota pontos
        if len(pontos_gdf) > 0:
            for cep in pontos_gdf['cep'].unique():
                pontos_cep = pontos_gdf[pontos_gdf['cep'] == cep]
                tamanho = pontos_cep.iloc[0]['tamanho']
                transparencia = pontos_cep.iloc[0]['transparencia']
                ax_mapa.scatter(pontos_cep.geometry.x, pontos_cep.geometry.y,
                                color=CONFIG["cores"]["pontos"],
                                s=tamanho, alpha=transparencia,
                                edgecolors='none', zorder=2)
        
        # Adiciona gráfico de barras no canto inferior esquerdo
        try:
            # Prepara dados - top 5 bairros
            dados_grafico = df_agg[df_agg['ano'] == ano].nlargest(5, 'quantidade_vinculos_ativos')
            
            if len(dados_grafico) > 0 and dados_grafico['percentual'].sum() > 0:
                # Cria eixo para o gráfico de barras (canto inferior esquerdo)
                ax_grafico = plt.axes([0.08, 0.08, 0.28, 0.28])
                
                # Cores
                bars = ax_grafico.barh(dados_grafico['bairro_nome'].str.title(), 
                                      dados_grafico['percentual'], 
                                      color=CONFIG["cores"]["pontos"], 
                                      alpha=0.85, edgecolor=CONFIG["cores"]["bordas"], linewidth=0.6)
                
                # Adiciona valores nas barras
                for i, (bar, valor) in enumerate(zip(bars, dados_grafico['percentual'])):
                    ax_grafico.text(bar.get_width() + 0.2, bar.get_y() + bar.get_height()/2,
                                   f'{valor:.1f}%', 
                                   va='center', 
                                   fontsize=CONFIG["fonte"]["legenda"] - 2,
                                   color=CONFIG["cores"]["texto"],
                                   weight='bold')
                
                # Configurações do gráfico
                ax_grafico.set_facecolor('none')
                ax_grafico.set_zorder(3)
                
                # Remove spines e ticks
                for spine in ax_grafico.spines.values():
                    spine.set_visible(False)
                ax_grafico.tick_params(axis='both', which='both', length=0)
                ax_grafico.grid(axis='x', color=CONFIG["cores"]["bordas"], alpha=0.2, linestyle='-', linewidth=0.5)
                
                # Configura eixos
                max_percentual = max(dados_grafico['percentual'])
                if max_percentual > 0:
                    ax_grafico.set_xlim(0, max_percentual * 1.3)
                ax_grafico.set_xticks([])
                
                # Labels dos bairros
                ax_grafico.set_yticklabels([nome[:12] + '...' if len(nome) > 12 else nome 
                                           for nome in dados_grafico['bairro_nome'].str.title()],
                                           fontsize=CONFIG["fonte"]["legenda"] - 2,
                                           color=CONFIG["cores"]["texto"])
                
                # Título do gráfico
                ax_grafico.text(0.5, 1.05, f'Maiores bairros', 
                               transform=ax_grafico.transAxes,
                               fontsize=CONFIG["fonte"]["legenda"],
                               color=CONFIG["cores"]["texto"],
                               weight='bold',
                               ha='center')
        except Exception as e:
            print(f"     Erro ao adicionar gráfico: {e}")
        
        # Adiciona labels dos 5 maiores bairros
        top5 = df_agg[df_agg['ano'] == ano].nlargest(5, 'quantidade_vinculos_ativos')
        for _, row in top5.iterrows():
            nome = row['bairro_nome']
            bairro_data = dados_mapa[dados_mapa['bairro'] == nome]
            if not bairro_data.empty and bairro_data['quantidade_vinculos_ativos'].iloc[0] > 0:
                centroid = bairro_data.geometry.centroid.iloc[0]
                # vinculos = int(bairro_data['quantidade_vinculos_ativos'].iloc[0])
                # percentual = float(bairro_data['percentual'].iloc[0])
                label_text = f"{nome.title()}" #f"{nome.title()}\n{vinculos:,} ({percentual:.1f}%)"
                ax_mapa.text(
                    centroid.x, centroid.y,
                    label_text,
                    fontsize=CONFIG["fonte"]["label"],
                    ha='center',
                    va='center',
                    color=CONFIG["cores"]["labels"],
                    weight='bold',
                    alpha=0.35
                )
        
        # Configurações do mapa
        ax_mapa.set_axis_off()
        ax_mapa.set_aspect('equal')
        
        # Título e subtítulo com estilo R
        titulo = f"Onde estavam os empregos formais em Teresina em {ano}?"
        
        # Top 3 bairros para subtítulo
        top_bairros = df_agg[df_agg['ano'] == ano].nlargest(3, 'quantidade_vinculos_ativos')
        subtitulo = f"{', '.join(top_bairros['bairro_nome'].str.title().tolist())} eram as regiões com mais empregos formais"
        
        # Adiciona título e subtítulo
        fig.text(0.05, 0.95, titulo, 
                fontsize=CONFIG["fonte"]["titulo"], 
                color=CONFIG["cores"]["texto"],
                weight='bold',
                family='sans-serif')
        
        fig.text(0.05, 0.92, subtitulo, 
                fontsize=CONFIG["fonte"]["subtitulo"], 
                color=CONFIG["cores"]["texto"],
                alpha=0.8,
                family='sans-serif')
        
        # Legenda estilizada (ajustada para não sobrepor o gráfico)
        total_vinculos = dados_mapa["quantidade_vinculos_ativos"].sum()
        legenda_text = f"Dispersão real dos CEPs\nTotal: {total_vinculos:,} empregos formais"
        
        fig.text(0.35, 0.02, legenda_text, 
                fontsize=CONFIG["fonte"]["legenda"], 
                color=CONFIG["cores"]["legenda"],
                bbox=dict(boxstyle='round,pad=0.5', 
                         facecolor=CONFIG["cores"]["fundo_claro"], 
                         alpha=0.9,
                         edgecolor=CONFIG["cores"]["bordas"]))
        
        # Salva com fundo escuro
        plt.tight_layout()
        fig.savefig(output_path, dpi=300, bbox_inches='tight', 
                   facecolor=CONFIG["cores"]["fundo"], edgecolor='none')
        plt.close()
        
        print(f"   ✓ Mapa salvo: {output_path.name}")
    
    def gerar_grafico_barras(self, df_agg: pd.DataFrame, ano: int, output_path: Path):
        """Gera gráfico de barras estilo R para o ano específico"""
        print(f" Gerando gráfico de barras para {ano}...")
        
        # Prepara dados - top 5 bairros
        dados_ano = df_agg[df_agg['ano'] == ano].nlargest(5, 'quantidade_vinculos_ativos')
        
        # Verifica se há dados válidos
        if len(dados_ano) == 0 or dados_ano['percentual'].sum() == 0:
            print(f"     Nenhum dado válido para {ano}, pulando gráfico")
            return
        
        # Cria figura com estilo dark theme
        fig, ax = plt.subplots(figsize=(8, 6), dpi=300)
        
        # Cores
        bars = ax.barh(dados_ano['bairro_nome'].str.title(), 
                      dados_ano['percentual'], 
                      color=CONFIG["cores"]["pontos"], 
                      alpha=0.8)
        
        # Adiciona valores nas barras
        for i, (bar, valor) in enumerate(zip(bars, dados_ano['percentual'])):
            ax.text(bar.get_width() + 0.2, bar.get_y() + bar.get_height()/2,
                   f'{valor:.1f}%', 
                   va='center', 
                   fontsize=CONFIG["fonte"]["legenda"],
                   color=CONFIG["cores"]["texto"],
                   weight='bold')
        
        # Configurações do gráfico
        ax.set_facecolor(CONFIG["cores"]["fundo_claro"])
        fig.patch.set_facecolor(CONFIG["cores"]["fundo"])
        
        # Remove spines e ticks
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_visible(False)
        ax.spines['left'].set_visible(False)
        ax.tick_params(axis='both', which='both', length=0)
        
        # Configura eixos com validação
        max_percentual = max(dados_ano['percentual'])
        if max_percentual > 0:
            ax.set_xlim(0, max_percentual * 1.3)
        ax.set_xticks([])
        ax.set_yticklabels([])
        
        # Título
        fig.text(0.05, 0.95, f'Top 5 Bairros - {ano}', 
                fontsize=CONFIG["fonte"]["titulo"], 
                color=CONFIG["cores"]["texto"],
                weight='bold')
        
        # Salva
        plt.tight_layout()
        fig.savefig(output_path, dpi=300, bbox_inches='tight', 
                   facecolor=CONFIG["cores"]["fundo"], edgecolor='none')
        plt.close()
        
        print(f"   ✓ Gráfico salvo: {output_path.name}")
    
    def gerar_relatorio(self, df_agg: pd.DataFrame, output_path: Path):
        """Gera relatório estatístico"""
        print("\n Gerando relatório...")
        
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
        print("Iniciando processamento de dados RAIS...")
        print("=" * 50)
        
        # Carrega dados
        df, shp = self.carregar_dados()
        
        # Atribui bairros
        df_com_bairros = self.atribuir_bairros(df, shp)
        
        # Agrega dados
        df_agg = self.agregar_dados(df_com_bairros)
        
        # Gera mapas para cada ano (com gráfico integrado)
        output_dir = self.data_dir.parent / "output"
        output_dir.mkdir(exist_ok=True)
        
        for ano in CONFIG["anos_analise"]:
            mapa_path = output_dir / f"mapa_emprego_teresina_{ano}.png"
            self.gerar_mapa_com_grafico(df, df_agg, shp, ano, mapa_path)
        
        # Gera relatório
        relatorio_path = output_dir / "relatorio_emprego_teresina.txt"
        self.gerar_relatorio(df_agg, relatorio_path)
        
        print("\n" + "=" * 50)
        print("Processamento concluído com sucesso!")
        print(f"Arquivos salvos em: {output_dir}")


def main():
    """Função principal"""
    # Configurações - ajusta caminho para pasta data no diretório pai
    script_dir = Path(__file__).parent
    data_dir = script_dir.parent / "data"
    output_dir = script_dir.parent / "output"
    
    # Cria diretório de saída se não existir
    output_dir.mkdir(exist_ok=True)
    
    # Verifica se arquivos existem
    arquivos_necessarios = [
        data_dir / "BAIRROS_2013.shp",
        data_dir / "ceps_com_coordenadas_otimizado.csv"
    ]
    
    for arquivo in arquivos_necessarios:
        if not arquivo.exists():
            print(f"Arquivo não encontrado: {arquivo}")
            return
    
    # Executa processamento
    processador = ProcessadorRAIS(data_dir)
    processador.executar()


if __name__ == "__main__":
    main()
