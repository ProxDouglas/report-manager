# Skill de proteção de dados sensíveis

## Objetivo

Orientar os serviços de backend que catalogam fontes, validam consultas, montam o contexto da IA e geram arquivos. A skill reduz o risco de expor credenciais, identificadores pessoais e outros dados restritos.

Esta skill é uma política de aplicação. Ela não substitui autenticação, autorização, criptografia, segregação por organização, revisão humana ou os limites do RestrictedPython e do Docker.

## Classificações mínimas

Toda tabela, coluna, métrica, amostra e resultado deve possuir uma classificação. Quando não houver informação suficiente, usar a classificação mais restritiva até a revisão de um responsável.

| Classificação | Exemplos | Regra padrão |
|---|---|---|
| `PUBLICO` | Código de produto não sensível, data de referência | Pode ser usado no relatório conforme a permissão |
| `INTERNO` | Indicadores operacionais e nomes de áreas | Não sair da organização |
| `CONFIDENCIAL` | Dados financeiros internos, contratos e margens | Exigir permissão específica e minimizar a exposição |
| `SENSIVEL` | CPF, CNPJ, telefone, endereço, dados pessoais | Mascarar, agregar ou bloquear conforme a finalidade |
| `SECRETO` | Senha, token, API key, string de conexão, chave privada | Bloquear sempre para telas, IA, logs e arquivos |

## Detecção inicial

A detecção automática deve combinar sinais. Nenhum sinal isolado deve ser tratado como prova definitiva.

1. **Nome do campo**: procurar termos como `senha`, `password`, `pass`, `token`, `secret`, `api_key`, `authorization`, `cpf`, `cnpj`, `documento`, `email`, `telefone` e equivalentes configurados pelo cliente.
2. **Tipo e metadados**: considerar tipo, comentário da coluna, tabela de origem, máscara já informada pelo cliente e sistema proprietário.
3. **Formato**: validar padrões de CPF e CNPJ somente sobre valores temporários e controlados; não persistir a amostra usada na validação.
4. **Contexto**: uma coluna chamada `id` não deve ser marcada como pública apenas pelo nome. A decisão depende da origem, do relacionamento e da política da organização.
5. **Confiança**: registrar `ALTA`, `MEDIA` ou `BAIXA` e o motivo da sugestão. A classificação confirmada pelo administrador prevalece sobre a inferência automática.

## Regras obrigatórias

- Nunca registrar senha, token, API key, string de conexão ou chave privada em log, exceção, auditoria, prompt, resposta da IA, arquivo de saída ou mensagem de erro.
- Nunca enviar valores brutos de CPF ou CNPJ para o LLM. Se a análise exigir identificação, usar máscara, hash não reversível ou agregação aprovada.
- Não enviar amostras de dados para a IA por padrão. Metadados de tabela, nomes de coluna e definições de métricas são preferíveis.
- Não permitir seleção de campos `SECRETO` em consultas geradas manualmente ou pela IA.
- Não confiar apenas no frontend. A classificação e o bloqueio devem ser aplicados na API, no serviço de consulta, no coletor e no gerador de arquivos.
- Aplicar a política da organização antes de materializar o snapshot que será entregue ao pipeline.
- Aplicar mascaramento antes de exibir na tela, exportar, enviar por e-mail ou publicar em webhook.
- Limpar arquivos temporários e amostras após a execução, conforme a política de retenção.

## Ações permitidas por classificação

O serviço deve escolher uma ação explícita para cada campo:

- `PERMITIR`: campo pode ser usado no escopo autorizado;
- `MASCARAR`: mostrar somente parte não identificadora, como `***.***.***-09`;
- `AGREGAR`: permitir somente contagem, soma, média ou outra agregação aprovada;
- `TOKENIZAR`: substituir o valor por identificador não reversível quando a correlação for necessária;
- `BLOQUEAR`: impedir seleção, transmissão e geração de resultado.

Para `SECRETO`, a ação padrão é sempre `BLOQUEAR`. Para `SENSIVEL`, a ação padrão é `MASCARAR` ou `AGREGAR`, conforme o tipo de relatório.

## Contrato sugerido do serviço

O serviço de proteção deve receber metadados e devolver uma decisão verificável, sem devolver valores sensíveis:

```text
classificacao = classificar(catalogo, politica_da_organizacao)
decisao = avaliar_uso(campo, finalidade, identidade, classificacao)
resultado = aplicar_politica(resultado_bruto, decisoes)
```

Cada decisão deve conter, no mínimo:

- identificador da organização;
- identificador da fonte, versão e campo;
- classificação e confiança;
- ação aplicada;
- regra que justificou a ação;
- versão da política;
- responsável e data da revisão, quando houver.

O campo `valor` não deve fazer parte da auditoria dessa decisão.

## Testes mínimos

- Uma coluna `password_hash` não aparece no catálogo utilizável pela IA.
- Uma coluna `api_key` não aparece em log mesmo quando a conexão falha.
- CPF e CNPJ são mascarados ou agregados antes de tela, CSV, XLSX, PDF, e-mail e webhook.
- A tentativa de contornar o bloqueio usando SQL manual ou código Python é rejeitada antes da execução.
- A classificação permanece associada à versão da fonte usada na execução.
- Uma alteração de política é auditada e não altera retroativamente o arquivo histórico já gerado.

