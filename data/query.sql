SELECT
  e.id_municipio,
  -- e.razao_social,
  e.cep,
  -- e.logradouro,
  -- e.numero,
  -- e.complemento,
  e.quantidade_vinculos_ativos,
  e.ano
FROM `basedosdados.br_me_rais.microdados_estabelecimentos` e
WHERE e.id_municipio = "2211001"  -- Teresina (IBGE)
  AND e.ano IN (2004, 2023)
  AND e.quantidade_vinculos_ativos > 0
  AND e.cep IS NOT NULL
  AND e.cep != '99999999'  -- Exclui CEPs "não informado"
-- ORDER BY e.ano, e.razao_social, e.cep;
