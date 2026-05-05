# Feature Completa — Instagram Link Intelligence para SignalVault

## Objetivo

Na página **/library**, a plataforma deve reconhecer links do Instagram existentes no acervo.  
Se o usuário possuir a integração **Conectar Instagram** ativa, o sistema utilizará a autorização da conta para acessar o conteúdo do link, extrair informações e gerar inteligência automática.

O resultado será exibido em **/content/{id}**.

---

## Proposta de Valor

Transformar links salvos do Instagram em conteúdo pesquisável e analisado automaticamente.

### Exemplo

**Antes**

```text
https://instagram.com/p/ABC123
```

**Depois**

```text
Resumo do post
Tom da comunicação
Texto presente na imagem
CTA identificado
Nicho
Sentimento
Tags inteligentes
```

---

## Escopo Funcional

### Em /library

O sistema deve identificar automaticamente links compatíveis:

```text
instagram.com/p/
instagram.com/reel/
instagram.com/reels/
instagram.com/tv/
```

Ao detectar:

```text
source_platform = instagram
processing_status = pending
```

---

## Pré-Requisito

Usuário precisa conectar sua conta do Instagram via integração oficial.

```text
/settings/integrations
[ Conectar Instagram ]
```

Se não conectado:

```text
Conecte sua conta Instagram para habilitar análise automática de links.
```

---

## Fluxo Completo

```text
Link encontrado em /library
↓
Verificar integração Instagram ativa
↓
Enviar item para fila assíncrona
↓
Acessar post autorizado
↓
Ler legenda e metadata
↓
Ler imagens temporariamente
↓
Detectar texto visual (OCR)
↓
Executar IA contextual
↓
Salvar somente resultados textuais
↓
Exibir análise em /content/{id}
```

---

## Processamento Técnico

### 1. Coleta do Post

Extrair:

- permalink
- caption
- timestamp
- tipo de mídia
- autor/perfil (quando disponível)
- múltiplas imagens (carrossel)

### 2. Análise das Imagens (sem salvar arquivos)

As imagens serão acessadas temporariamente em memória.

**Objetivos:**

- detectar texto
- entender contexto visual
- identificar marketing/promocional
- detectar presença de preço/oferta
- identificar estilo visual

### 3. OCR (Reconhecimento de Texto)

Se houver texto na imagem, ler automaticamente.

```text
NOVA COLEÇÃO
40% OFF
FRETE GRÁTIS
```

---

## Campos Analíticos Gerados

```json
{
  "summary": "Post promocional sobre moda fitness",
  "tone": "motivacional",
  "niche": "fitness feminino",
  "cta": "compre agora",
  "tags": ["instagram", "fitness", "roupa"],
  "ocr_text": "Nova coleção 40% OFF",
  "confidence_score_ocr": 0.94,
  "language_detected": "pt-BR",
  "sentiment_score": 0.82
}
```

---

## Significado dos Novos Campos

### confidence_score_ocr

Probabilidade da leitura OCR estar correta.

```text
0.00 = baixa confiança
1.00 = alta confiança
```

Uso:

- destacar OCR ruim
- permitir reprocessamento
- filtrar resultados confiáveis

### language_detected

Idioma principal detectado no conjunto:

- legenda
- texto visual
- hashtags relevantes

Exemplos:

```text
pt-BR
en-US
es-ES
```

### sentiment_score

Mede carga emocional/comercial do conteúdo.

```text
-1.00 = negativo
0.00 = neutro
1.00 = positivo
```

Exemplo:

```text
0.82 = altamente positivo / motivacional
```

---

## Regras de Persistência

### Salvar

- legenda
- texto OCR
- resumo IA
- tom
- nicho
- CTA
- tags
- scores
- metadata textual

### Não salvar

- imagens
- vídeos
- thumbnails

---

## Banco de Dados

Tabela `content_items`:

```sql
source_platform
source_url
external_id
caption
ocr_text
summary
tone
niche
cta
tags_json
confidence_score_ocr
language_detected
sentiment_score
processing_status
processed_at
error_message
```

---

## Status de Processamento

```text
pending
processing
completed
failed
needs_instagram_connection
```

---

## UI em /library

```text
Instagram Link
Status: Processing...
Status: Completed
Status: Needs Connection
```

---

## UI em /content/{id}

### Seção Instagram Intelligence

```text
Resumo: Post promocional sobre moda fitness
Tom: Motivacional
Nicho: Fitness feminino
CTA: Compre agora
Idioma: Português (Brasil)
Sentimento: 0.82 positivo
OCR: Nova coleção 40% OFF
Confiança OCR: 94%
```

### Tags

```text
instagram
fitness
roupa
promoção
marketing
```

---

## Worker Assíncrono

```python
process_instagram_content(content_id)
```

Etapas:

1. Buscar item
2. Validar integração
3. Ler conteúdo
4. OCR
5. IA contextualiza
6. Atualizar banco
7. Status completed

---

## Falhas Tratadas

### Link removido

```text
failed
Conteúdo indisponível
```

### Token expirado

```text
needs_instagram_connection
```

### OCR inválido

```text
confidence_score_ocr = 0.21
```

---

## Benefícios Estratégicos

### Para o usuário

Links viram conhecimento pesquisável.

### Para o produto

SignalVault deixa de ser “bookmark app”.

**Vira: Personal Social Intelligence Vault**

---

## Escalabilidade Futura

Mesmo motor pode processar links de:

- YouTube
- TikTok
- X
- LinkedIn

---

## Recomendação Final de Produto

Nome interno da feature:

- Instagram Insight Engine
- Smart Link Intelligence

---

## Resultado Esperado

Ao salvar um link do Instagram, o usuário não guarda só URL.

Ele guarda **inteligência extraída automaticamente**.
