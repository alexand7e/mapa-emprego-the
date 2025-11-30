Mapa do Emprego Formal em Teresina (RAIS)
=========================================

Projeto aberto voltado para aprendizado em economia e análise espacial do mercado de trabalho.
Usa dados da RAIS para visualizar a distribuição de empregos formais por CEP e por bairro em Teresina/PI.

Objetivos
---------
- Facilitar o estudo da geografia do emprego formal com dados públicos (RAIS).
- Oferecer um pipeline reproduzível de coleta, tratamento e visualização.
- Servir como material de apoio para estudantes e pesquisadores em economia regional.

Estrutura do Projeto
--------------------
- `data/`: arquivos de dados (RAIS, shapefile de bairros e caches de CEP).
  - `BAIRROS_2013.shp` (+ arquivos auxiliares `.cpg/.dbf/.prj/.shx`).
  - `empregos_rais.csv`.
  - `ceps_com_coordenadas_otimizado.csv` (gerado pelo pipeline).
- `src/`: scripts principais em Python.
  - `processar_ceps_otimizado.py`: prepara e georreferencia CEPs.
  - `emprego_formal_rais_teresina_coordenadas.py`: integra RAIS com coordenadas.
  - `infografico_emprego_teresina.py`: gera o mapa com gráfico integrado e relatório.
- `output/`: imagens e relatórios gerados.

Instalação (Python)
-------------------
Requisitos: Python 3.10+.

Instale as dependências principais:

```
pip install pandas geopandas matplotlib shapely pyproj
```

Como Executar
-------------
1) Preparar os CEPs e coordenadas:

```
python src/processar_ceps_otimizado.py
```

2) Gerar o infográfico e relatório:

```
python src/infografico_emprego_teresina.py
```

Saída
-----
- `output/mapa_emprego_teresina_2023.png`: mapa com dispersão real dos CEPs e gráfico dos top 5 bairros.
- `output/relatorio_emprego_teresina.txt`: estatísticas por ano e por bairro.

Resultados Recentes
-------------------
- Registros analisados: 17.744 (RAIS 2023)
- Vínculos totais: 323.435
- CEPs com coordenadas válidas: 17.696

Visualização gerada (2023):

![Mapa de empregos formais 2023](output/mapa_emprego_teresina_2023.png)

Relatório detalhado:

- [output/relatorio_emprego_teresina.txt](output/relatorio_emprego_teresina.txt)

Metodologia (resumo)
--------------------
- RAIS: soma de vínculos ativos por bairro e por ano.
- Geocodificação: uso de CEP com coordenadas associadas; pontos dentro dos polígonos de bairros.
- Visualização:
  - Tamanho e transparência dos pontos proporcional ao número de empregos por CEP.
  - Redução de sobreposição em CEPs com muitos empregos.
  - Gráfico de barras com os 5 bairros de maior emprego.

Uso Educacional
---------------
- Conceitos-chave: vínculos, concentração espacial, heterogeneidade intraurbana.
- Possíveis exercícios:
  - Comparar a distribuição de empregos entre anos.
  - Calcular participação (%) dos top 5 e discutir mudanças estruturais.
  - Investigar clusters por zonas da cidade e relacionar com infraestrutura/serviços.

Contribuição
------------
- Sugestões e melhorias são bem-vindas via *issues* e *pull requests*.
- Priorize clareza e reprodutibilidade ao contribuir (scripts com passos explícitos).

Observações
-----------
- Este repositório foca aprendizado e pesquisa; valide resultados antes de uso aplicado.
- Coordenadas por CEP são aproximadas; podem existir vieses geográficos.

Exemplos de Infográficos
------------------------
<img width="2920" height="2203" alt="mapa_com_grafico_2004" src="https://github.com/user-attachments/assets/1a488397-0967-4b30-9333-1a2906ef5e55" />

<img width="2901" height="2170" alt="mapa_com_grafico_2024" src="https://github.com/user-attachments/assets/3a5cee4f-1ee9-4b16-a1a6-a8ffdc8a0248" />
