# Contrato da API (rascunho)

> **Estado: rascunho para revisão do grupo.** Nada disto está implementado; o esqueleto só tem `GET /health` em cada serviço. As decisões ainda por fechar estão em [Pontos em aberto](#pontos-em-aberto).

## Convenções

- **URL pública:** tudo passa pelo gateway, em `http://localhost:8080`. A coluna "Rota no serviço" indica o caminho que o serviço recebe.
- **Autenticação:** cabeçalho `Authorization: Bearer <token>`. O token é emitido por `users` e validado localmente em cada serviço.
- **Erros:** formato do FastAPI, `{"detail": "mensagem"}`. Erros de validação devolvem `422`.
- **Valores monetários:** inteiros em cêntimos de euro (`price_cents`, `total_cents`, `amount_cents`).
- **Identificadores:** UUID.
- **Tamanhos:** texto na numeração europeia (por exemplo, `"42"` ou `"42.5"`).

### Mapeamento do gateway

| Caminho público | Rota no serviço | Serviço |
|---|---|---|
| `/api/auth/...` | `/auth/...` | users |
| `/api/users/...` | `/users/...` | users |
| `/api/catalog/...` | `/...` | catalog |
| `/api/orders`, `/api/orders/...` | `/orders`, `/orders/...` | orders |
| `/api/payments`, `/api/payments/...` | `/payments`, `/payments/...` | payments |
| `/api/<serviço>/health`, `/docs`, `/openapi.json` | `/health`, `/docs`, `/openapi.json` | cada serviço |
| Qualquer caminho com um segmento `internal` | Bloqueado com `404` | nenhum |

---

## Serviço users

**Responsável:** Gustavo

### Endpoints

| Método e rota pública | Rota no serviço | Autenticação | Descrição |
|---|---|---|---|
| `POST /api/auth/register` | `POST /auth/register` | Não | Regista um utilizador |
| `POST /api/auth/login` | `POST /auth/login` | Não | Autentica e devolve um JWT |
| `GET /api/users/me` | `GET /users/me` | JWT | Devolve o perfil do utilizador autenticado |
| `PUT /api/users/me` | `PUT /users/me` | JWT | Atualiza o perfil do utilizador autenticado |

#### `POST /api/auth/register`

**Request**

```json
{ "email": "ana@example.com", "password": "uma-palavra-passe", "name": "Ana Silva" }
```

**Response `201`**

```json
{ "id": "uuid", "email": "ana@example.com", "name": "Ana Silva", "role": "customer" }
```

**Códigos de erro:** `409` email já registado; `422` dados inválidos.

#### `POST /api/auth/login`

**Request**

```json
{ "email": "ana@example.com", "password": "uma-palavra-passe" }
```

**Response `200`**

```json
{ "access_token": "jwt", "token_type": "bearer", "expires_in": 3600 }
```

**Códigos de erro:** `401` credenciais inválidas; `422` dados inválidos.

**Claims do JWT:** `sub` (id do utilizador), `email`, `role` (`customer` ou `admin`), `iat`, `exp`.

#### `GET /api/users/me`

**Response `200`**

```json
{ "id": "uuid", "email": "ana@example.com", "name": "Ana Silva", "role": "customer" }
```

**Códigos de erro:** `401` token em falta, inválido ou expirado.

#### `PUT /api/users/me`

**Request**

```json
{ "name": "Ana Maria Silva" }
```

**Response `200`:** o mesmo formato de `GET /api/users/me`.

**Códigos de erro:** `401` token em falta, inválido ou expirado; `422` dados inválidos.

### Modelo de dados

**`users`**

| Campo | Tipo | Notas |
|---|---|---|
| `id` | UUID | Chave primária |
| `email` | texto | Único |
| `password_hash` | texto | bcrypt; a palavra-passe nunca é guardada em claro |
| `name` | texto | |
| `role` | texto | `customer` ou `admin` |
| `created_at` | timestamp | |

---

## Serviço catalog

**Responsável:** Sergio

### Endpoints

| Método e rota pública | Rota no serviço | Autenticação | Descrição |
|---|---|---|---|
| `GET /api/catalog/products` | `GET /products` | Não | Lista modelos; filtros `q`, `brand`, `size` |
| `GET /api/catalog/products/{id}` | `GET /products/{id}` | Não | Detalhe do modelo, com stock por tamanho |
| `GET /api/catalog/products/{id}/availability?size=` | `GET /products/{id}/availability?size=` | Não | Disponibilidade de um tamanho |
| `POST /api/catalog/products` | `POST /products` | JWT `admin` | Cria um modelo |
| `PUT /api/catalog/products/{id}` | `PUT /products/{id}` | JWT `admin` | Atualiza um modelo |
| `DELETE /api/catalog/products/{id}` | `DELETE /products/{id}` | JWT `admin` | Remove um modelo |
| Não exposta | `POST /internal/stock/decrement` | Só rede interna | Desconta stock de forma atómica |

#### `GET /api/catalog/products`

**Response `200`**

```json
[
  { "id": "uuid", "brand": "Marca", "name": "Modelo", "price_cents": 8999, "image_url": "/img/modelo.jpg" }
]
```

#### `GET /api/catalog/products/{id}`

**Response `200`**

```json
{
  "id": "uuid",
  "brand": "Marca",
  "name": "Modelo",
  "description": "Descrição",
  "price_cents": 8999,
  "image_url": "/img/modelo.jpg",
  "sizes": [{ "size": "42", "stock": 3 }]
}
```

**Códigos de erro:** `404` modelo inexistente.

#### `GET /api/catalog/products/{id}/availability?size=42`

**Response `200`**

```json
{ "product_id": "uuid", "size": "42", "stock": 3, "available": true, "price_cents": 8999 }
```

**Códigos de erro:** `404` modelo ou tamanho inexistente; `422` parâmetro `size` em falta.

#### `POST /api/catalog/products` e `PUT /api/catalog/products/{id}`

**Request**

```json
{
  "brand": "Marca",
  "name": "Modelo",
  "description": "Descrição",
  "price_cents": 8999,
  "image_url": "/img/modelo.jpg",
  "sizes": [{ "size": "42", "stock": 3 }]
}
```

**Response:** `201` no `POST` e `200` no `PUT`, com o mesmo formato de `GET /api/catalog/products/{id}`.

**Códigos de erro:** `401` sem autenticação; `403` utilizador sem papel `admin`; `404` modelo inexistente (`PUT`); `422` dados inválidos.

#### `DELETE /api/catalog/products/{id}`

**Response `204`:** sem corpo.

**Códigos de erro:** `401` sem autenticação; `403` utilizador sem papel `admin`; `404` modelo inexistente.

#### `POST /internal/stock/decrement`

Chamado por `orders` depois de `payment.confirmed`. Todas as linhas são descontadas na mesma transação: ou passam todas, ou nenhuma. Cada linha usa `UPDATE ... SET stock = stock - :quantity WHERE ... AND stock >= :quantity`.

**Request**

```json
{
  "order_id": "uuid",
  "items": [{ "product_id": "uuid", "size": "42", "quantity": 1 }]
}
```

**Response `200`**

```json
{ "order_id": "uuid", "decremented": true }
```

**Códigos de erro:** `404` modelo ou tamanho inexistente; `409` stock insuficiente (nada é descontado).

### Modelo de dados

**`products`**

| Campo | Tipo | Notas |
|---|---|---|
| `id` | UUID | Chave primária |
| `brand` | texto | |
| `name` | texto | |
| `description` | texto | |
| `price_cents` | inteiro | `>= 0` |
| `image_url` | texto | |
| `created_at` | timestamp | |

**`product_sizes`**

| Campo | Tipo | Notas |
|---|---|---|
| `product_id` | UUID | Chave estrangeira para `products`; chave primária com `size` |
| `size` | texto | |
| `stock` | inteiro | `CHECK (stock >= 0)` |

**`stock_decrements`** (idempotência)

| Campo | Tipo | Notas |
|---|---|---|
| `order_id` | UUID | Chave primária; impede que a mesma encomenda desconte stock duas vezes |
| `created_at` | timestamp | |

---

## Serviço orders

**Responsável:** Diogo

### Endpoints

| Método e rota pública | Rota no serviço | Autenticação | Descrição |
|---|---|---|---|
| `POST /api/orders` | `POST /orders` | JWT | Cria uma encomenda |
| `GET /api/orders` | `GET /orders` | JWT | Lista as encomendas do utilizador |
| `GET /api/orders/{id}` | `GET /orders/{id}` | JWT | Detalhe de uma encomenda do utilizador |

#### `POST /api/orders`

**Request**

```json
{ "items": [{ "product_id": "uuid", "size": "42", "quantity": 1 }] }
```

**Response `201`**

```json
{
  "id": "uuid",
  "status": "PENDING_PAYMENT",
  "total_cents": 8999,
  "items": [{ "product_id": "uuid", "size": "42", "quantity": 1, "unit_price_cents": 8999 }],
  "created_at": "2026-11-02T10:00:00Z"
}
```

**Códigos de erro:** `401` sem autenticação; `404` modelo ou tamanho inexistente; `409` stock insuficiente; `422` dados inválidos; `503` `catalog` indisponível.

#### `GET /api/orders`

**Response `200`:** lista com o formato de `POST /api/orders`.

**Códigos de erro:** `401` sem autenticação.

#### `GET /api/orders/{id}`

**Response `200`:** o formato de `POST /api/orders`.

**Códigos de erro:** `401` sem autenticação; `404` encomenda inexistente ou de outro utilizador.

### Estados da encomenda

| Estado | Significado |
|---|---|
| `PENDING_PAYMENT` | Criada, com stock verificado, à espera de pagamento |
| `PAID` | Pagamento confirmado, stock ainda por descontar |
| `CONFIRMED` | Stock descontado; estado final de sucesso |
| `PAYMENT_FAILED` | Pagamento rejeitado; estado final |
| `CANCELLED` | Compensação: o stock esgotou-se depois do pagamento; estado final |

```
PENDING_PAYMENT ──payment.confirmed──► PAID ──stock descontado──► CONFIRMED
       │                                │
       └──payment.failed──► PAYMENT_FAILED
                                        └──stock insuficiente──► CANCELLED
```

### Modelo de dados

**`orders`**

| Campo | Tipo | Notas |
|---|---|---|
| `id` | UUID | Chave primária |
| `user_id` | UUID | Sem chave estrangeira: o utilizador está noutra base de dados |
| `status` | texto | Um dos estados acima |
| `total_cents` | inteiro | |
| `created_at` | timestamp | |
| `updated_at` | timestamp | |

**`order_items`**

| Campo | Tipo | Notas |
|---|---|---|
| `id` | UUID | Chave primária |
| `order_id` | UUID | Chave estrangeira para `orders` |
| `product_id` | UUID | Sem chave estrangeira: o modelo está noutra base de dados |
| `size` | texto | |
| `quantity` | inteiro | `> 0` |
| `unit_price_cents` | inteiro | Preço no momento da compra |

**`processed_events`** (idempotência)

| Campo | Tipo | Notas |
|---|---|---|
| `event_id` | UUID | Chave primária; o JetStream pode entregar a mesma mensagem mais do que uma vez |
| `processed_at` | timestamp | |

---

## Serviço payments

**Responsável:** Gustavo

### Endpoints

| Método e rota pública | Rota no serviço | Autenticação | Descrição |
|---|---|---|---|
| `POST /api/payments` | `POST /payments` | JWT | Executa um pagamento simulado |

#### `POST /api/payments`

O montante não vem do cliente: `payments` obtém-no com `GET /orders/{id}` em `orders`, reencaminhando o JWT do utilizador. Um cartão terminado em `0000` é rejeitado; qualquer outro é aceite. Guardam-se apenas os últimos quatro dígitos.

**Request**

```json
{ "order_id": "uuid", "card_number": "4242424242424242" }
```

**Response `201`**

```json
{ "id": "uuid", "order_id": "uuid", "amount_cents": 8999, "status": "CONFIRMED", "card_last4": "4242" }
```

Com um cartão rejeitado, a resposta é a mesma mas com `"status": "FAILED"`, e o evento publicado é `payment.failed`.

**Códigos de erro:** `401` sem autenticação; `404` encomenda inexistente ou de outro utilizador; `409` encomenda fora do estado `PENDING_PAYMENT`; `422` dados inválidos; `503` `orders` indisponível.

### Modelo de dados

**`payments`**

| Campo | Tipo | Notas |
|---|---|---|
| `id` | UUID | Chave primária |
| `order_id` | UUID | Sem chave estrangeira: a encomenda está noutra base de dados |
| `user_id` | UUID | |
| `amount_cents` | inteiro | |
| `status` | texto | `CONFIRMED` ou `FAILED` |
| `card_last4` | texto | Nunca se guarda o número completo |
| `created_at` | timestamp | |

---

## Eventos (NATS JetStream)

Todos os eventos usam o mesmo envelope. O assunto (*subject*) NATS é igual a `type`. Como o JetStream entrega pelo menos uma vez, os consumidores têm de ignorar um `event_id` já processado.

```json
{
  "event_id": "uuid",
  "type": "payment.confirmed",
  "occurred_at": "2026-11-02T10:00:00Z",
  "data": {}
}
```

| Evento | Publicador | Consumidor | Efeito |
|---|---|---|---|
| `payment.confirmed` | payments | orders | `PENDING_PAYMENT` → `PAID`, seguido do desconto de stock |
| `payment.failed` | payments | orders | `PENDING_PAYMENT` → `PAYMENT_FAILED` |
| `order.confirmed` | orders | A definir | Informa que a encomenda ficou `CONFIRMED` |

### `payment.confirmed`

```json
{
  "event_id": "uuid",
  "type": "payment.confirmed",
  "occurred_at": "2026-11-02T10:00:00Z",
  "data": {
    "payment_id": "uuid",
    "order_id": "uuid",
    "user_id": "uuid",
    "amount_cents": 8999
  }
}
```

### `payment.failed`

```json
{
  "event_id": "uuid",
  "type": "payment.failed",
  "occurred_at": "2026-11-02T10:00:00Z",
  "data": {
    "payment_id": "uuid",
    "order_id": "uuid",
    "user_id": "uuid",
    "amount_cents": 8999,
    "reason": "CARD_DECLINED"
  }
}
```

### `order.confirmed`

```json
{
  "event_id": "uuid",
  "type": "order.confirmed",
  "occurred_at": "2026-11-02T10:00:05Z",
  "data": {
    "order_id": "uuid",
    "user_id": "uuid",
    "total_cents": 8999,
    "items": [{ "product_id": "uuid", "size": "42", "quantity": 1 }]
  }
}
```

---

## Pontos em aberto

Propostas acrescentadas neste rascunho, a confirmar pelo grupo:

1. **Quem inicia o pagamento.** Aqui é o cliente, com `POST /api/payments`, para que o número do cartão não passe por `orders`. Por isso `payments` chama `orders` por HTTP para obter o montante.
2. **Reembolso na compensação.** Quando o stock se esgota, a encomenda passa a `CANCELLED` e o pagamento tem de ser anulado (reembolso simulado). Falta um mecanismo: a proposta é acrescentar um evento `order.cancelled`, consumido por `payments`, e um estado `REFUNDED` no pagamento.
3. **Consumidor de `order.confirmed`.** Nenhum serviço precisa dele no fluxo atual. Decidir se fica só como registo ou se alimenta alguma funcionalidade.
4. **Nova tentativa de pagamento.** `PAYMENT_FAILED` é aqui um estado final, pelo que uma nova tentativa implica criar outra encomenda.
5. **Algoritmo do JWT.** O `.env.example` usa HS256 com segredo partilhado, o que é simples, mas qualquer serviço conseguiria emitir tokens. A alternativa é RS256, em que só `users` tem a chave privada.
