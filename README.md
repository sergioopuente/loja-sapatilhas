# Sistema de Gestão de uma Loja de Sapatilhas

**Idioma:** [Português](#pt) · [Español](#es)

---

<a id="pt"></a>

# Versão em Português

## Sistema de Gestão de uma Loja de Sapatilhas

- **Unidade curricular:** Arquitetura Avançada de Sistemas
- **Universidade:** Universidade Autónoma de Lisboa
- **Ano letivo:** 2026/2027
- **Docente:** Profa. Inês Almeida

## Descrição e objetivo

Sistema distribuído baseado em microsserviços para uma loja online fictícia de sapatilhas: catálogo de modelos, tamanhos e stock, utilizadores, encomendas e pagamentos simulados.

O objetivo é pôr em prática uma arquitetura distribuída, pelo que o foco está no back-end e a interface web é propositadamente simples. O projeto cumpre os requisitos obrigatórios do enunciado: Python, Docker, autenticação de utilizadores e quatro microsserviços que comunicam entre si.

> **Estado atual:** esqueleto do projeto. Cada serviço tem apenas o endpoint `GET /health`; a lógica de negócio descrita abaixo ainda está por implementar.

## Grupo e responsabilidades

| Membro | Responsabilidades |
|---|---|
| Gustavo | Microsserviço `users` + autenticação (módulo JWT partilhado) + microsserviço `payments` |
| Sergio | Microsserviço `catalog` (catálogo e stock por tamanho) + dados iniciais (seed) + frontend |
| Diogo | Microsserviço `orders` (orquestração da saga de compra) + infraestrutura (docker-compose, NATS, API gateway) |

## Arquitetura

```
                              Navegador
                                  │ HTTP (porto 8080 do host)
                                  ▼
  ┌──────────────────────────────────────────────────────────────┐
  │           API Gateway (Nginx) + frontend estático            │
  └────┬──────────────┬───────────────┬───────────────────┬──────┘
       ▼              ▼               ▼                   ▼
  ┌─────────┐    ┌─────────┐   ┌─────────────┐    ┌──────────────┐
  │  users  │    │ catalog │◄──│    orders   │◄───│   payments   │
  └────┬────┘    └────┬────┘   └────┬───────┬┘    └───┬────────┬─┘
       ▼              ▼             ▼       │         ▼        │
 ┌──────────┐  ┌────────────┐ ┌───────────┐ │ ┌─────────────┐  │
 │ users-db │  │ catalog-db │ │ orders-db │ │ │ payments-db │  │
 └──────────┘  └────────────┘ └───────────┘ │ └─────────────┘  │
                                            └────────┬─────────┘
                                                     ▼
                                           ┌───────────────────┐
                                           │   NATS JetStream  │
                                           └───────────────────┘

◄── HTTP síncrono (httpx): orders → catalog, payments → orders
│   orders e payments ligam-se ao NATS para publicar e consumir eventos
```

- Só o gateway publica um porto no host. Os serviços, as bases de dados e o NATS ficam acessíveis apenas na rede interna do Docker.
- Cada serviço acede unicamente à sua própria base de dados.
- As rotas `/internal/` não são expostas pelo gateway.

## Stack tecnológica

| Tecnologia | Justificação |
|---|---|
| Python 3.12 + FastAPI + Uvicorn | Python é obrigatório; o FastAPI valida dados e gera o Swagger automaticamente |
| PostgreSQL 16 (uma base de dados por serviço) | Padrão *database-per-service*: cada serviço é dono dos seus dados e não há acoplamento pelo esquema |
| SQLAlchemy + psycopg | Camada de acesso comum a todos os serviços, com transações para o desconto atómico de stock |
| HTTP com httpx | Comunicação síncrona quando é preciso uma resposta imediata, como a verificação de stock |
| NATS JetStream | Comunicação assíncrona com entrega persistente: um evento não se perde se o consumidor estiver em baixo |
| JWT + bcrypt | Cada serviço valida o token localmente, sem chamar `users` a cada pedido; o bcrypt protege as palavras-passe |
| Nginx | Ponto único de entrada: encaminha para os serviços, serve o frontend e esconde as rotas internas |
| HTML + JavaScript simples | A interface não é o foco do projeto, por isso não precisa de framework |
| Docker Compose | Arranca todo o sistema com um só comando; os *healthchecks* garantem a ordem de arranque |

## Serviços

| Serviço | Responsabilidade | Porto interno |
|---|---|---|
| `users` | Registo, login, emissão de JWT e perfil de utilizador | 8000 |
| `catalog` | Modelos, tamanhos e stock; desconto atómico de stock | 8000 |
| `orders` | Encomendas e orquestração da saga de compra | 8000 |
| `payments` | Pagamentos simulados e publicação dos respetivos eventos | 8000 |
| `users-db`, `catalog-db`, `orders-db`, `payments-db` | PostgreSQL de cada serviço | 5432 |
| `nats` | Mensageria com JetStream | 4222 |
| `gateway` | API Gateway e frontend estático | 80 (8080 no host) |

Cada serviço corre no seu próprio contentor, por isso todos podem usar o porto 8000.

## Fluxo de compra

O contrato completo está em [docs/api.md](docs/api.md).

1. **Criar a encomenda.** O cliente envia `POST /api/orders` com o seu JWT.
2. **Verificação síncrona de stock.** `orders` chama `catalog` por HTTP (`GET /products/{id}/availability?size=`) para cada linha. Sem stock, responde `409` e não cria nada. Com stock, a encomenda fica em `PENDING_PAYMENT`. O stock ainda não fica reservado.
3. **Pagamento simulado.** O cliente envia `POST /api/payments`. `payments` obtém o montante em `orders` e rejeita os cartões terminados em `0000`.
4. **Evento de pagamento.** `payments` publica `payment.confirmed` no NATS. Se o cartão for rejeitado, publica `payment.failed`, a encomenda passa a `PAYMENT_FAILED` e o fluxo termina.
5. **Desconto atómico de stock.** `orders` consome `payment.confirmed`, passa a encomenda a `PAID` e chama `POST /internal/stock/decrement` em `catalog`. Todas as linhas são descontadas numa só transação, e só se existir stock suficiente.
6. **Encomenda confirmada.** A encomenda passa a `CONFIRMED` e `orders` publica `order.confirmed`.

### Compensação (saga)

Entre os passos 2 e 5 há uma janela em que outro cliente pode comprar as últimas unidades. Nesse caso, o desconto responde `409` e não altera nada. Como o pagamento já foi feito e não há uma transação distribuída para reverter, a saga compensa: a encomenda passa a `CANCELLED` e o pagamento é anulado com um reembolso simulado.

O mecanismo do reembolso está por decidir; a proposta está nos [pontos em aberto](docs/api.md#pontos-em-aberto).

## Requisitos prévios

- Docker com Docker Compose v2
- Git

Não é preciso instalar Python no host: tudo corre dentro dos contentores.

## Como executar

```bash
cp .env.example .env
```

```bash
docker compose up --build
```

Altere os valores de `.env` se o ambiente for partilhado. O ficheiro `.env` não é guardado no Git. Se o porto 8080 estiver ocupado, mude `GATEWAY_PORT` no `.env`.

### URLs de acesso

| O quê | URL |
|---|---|
| Frontend | http://localhost:8080/ |
| Saúde de `users` | http://localhost:8080/api/users/health |
| Saúde de `catalog` | http://localhost:8080/api/catalog/health |
| Saúde de `orders` | http://localhost:8080/api/orders/health |
| Saúde de `payments` | http://localhost:8080/api/payments/health |

### Swagger de cada serviço

| Serviço | URL |
|---|---|
| `users` | http://localhost:8080/api/users/docs |
| `catalog` | http://localhost:8080/api/catalog/docs |
| `orders` | http://localhost:8080/api/orders/docs |
| `payments` | http://localhost:8080/api/payments/docs |

## Como executar os testes

Os testes correm dentro da imagem de cada serviço, com o Python 3.12 e as dependências certas:

```bash
docker compose run --rm --no-deps users pytest
```

```bash
docker compose run --rm --no-deps catalog pytest
```

```bash
docker compose run --rm --no-deps orders pytest
```

```bash
docker compose run --rm --no-deps payments pytest
```

Depois de alterar código ou testes, acrescente `--build` para reconstruir a imagem.

## Estrutura do repositório

```
.
├── docker-compose.yml
├── .env.example
├── .gitignore
├── .dockerignore
├── README.md
├── docs/
│   └── api.md              # Contrato da API, modelos de dados e eventos
├── frontend/
│   ├── index.html
│   └── app.js
├── gateway/
│   └── nginx.conf
├── shared/
│   └── auth/               # Módulo JWT comum
└── services/
    └── users | catalog | orders | payments
        ├── Dockerfile
        ├── pytest.ini
        ├── requirements.txt
        ├── app/
        │   ├── main.py
        │   ├── config.py
        │   ├── routes/
        │   ├── models/
        │   ├── schemas/
        │   └── db/
        └── tests/
            └── test_health.py
```

As imagens são construídas a partir da raiz do repositório para poderem copiar `shared/`.

## Fluxo de trabalho em Git

- **`main` protegida:** ninguém faz push direto para `main`.
- **Uma branch por funcionalidade:** `feat/<serviço>-<descrição>`, por exemplo `feat/catalog-filtros-produtos`.
- **Pull Requests:** cada alteração entra por Pull Request, com revisão de outro membro do grupo.
- **Commits convencionais:** por exemplo, `feat: adiciona login`, `fix: corrige desconto de stock`, `docs: atualiza contrato da API`.

## Datas-chave

| Marco | Data |
|---|---|
| Entrega (via e-learning) | 10 de janeiro de 2027, às 23:59 |
| Apresentação e Prova de Autoria (15 minutos) | Entre 11 e 23 de janeiro de 2027 |

---

<a id="es"></a>

# Versión en Español

## Sistema de Gestión de una Tienda de Zapatillas

- **Asignatura:** Arquitetura Avançada de Sistemas
- **Universidad:** Universidade Autónoma de Lisboa
- **Curso:** 2026/2027
- **Docente:** Profa. Inês Almeida

## Descripción y objetivo

Sistema distribuido basado en microservicios para una tienda online ficticia de zapatillas: catálogo de modelos, tallas y stock, usuarios, pedidos y pagos simulados.

El objetivo es poner en práctica una arquitectura distribuida, así que el foco está en el back-end y la interfaz web es deliberadamente simple. El proyecto cumple los requisitos obligatorios del enunciado: Python, Docker, autenticación de usuarios y cuatro microservicios que se comunican entre sí.

> **Estado actual:** esqueleto del proyecto. Cada servicio solo tiene el endpoint `GET /health`; la lógica de negocio descrita abajo aún está por implementar.

## Grupo y responsabilidades

| Miembro | Responsabilidades |
|---|---|
| Gustavo | Microservicio `users` + autenticación (módulo JWT compartido) + microservicio `payments` |
| Sergio | Microservicio `catalog` (catálogo y stock por talla) + datos semilla (seed) + frontend |
| Diogo | Microservicio `orders` (orquestación de la saga de compra) + infraestructura (docker-compose, NATS, API gateway) |

## Arquitectura

```
                              Navegador
                                  │ HTTP (puerto 8080 del host)
                                  ▼
  ┌──────────────────────────────────────────────────────────────┐
  │           API Gateway (Nginx) + frontend estático            │
  └────┬──────────────┬───────────────┬───────────────────┬──────┘
       ▼              ▼               ▼                   ▼
  ┌─────────┐    ┌─────────┐   ┌─────────────┐    ┌──────────────┐
  │  users  │    │ catalog │◄──│    orders   │◄───│   payments   │
  └────┬────┘    └────┬────┘   └────┬───────┬┘    └───┬────────┬─┘
       ▼              ▼             ▼       │         ▼        │
 ┌──────────┐  ┌────────────┐ ┌───────────┐ │ ┌─────────────┐  │
 │ users-db │  │ catalog-db │ │ orders-db │ │ │ payments-db │  │
 └──────────┘  └────────────┘ └───────────┘ │ └─────────────┘  │
                                            └────────┬─────────┘
                                                     ▼
                                           ┌───────────────────┐
                                           │   NATS JetStream  │
                                           └───────────────────┘

◄── HTTP síncrono (httpx): orders → catalog, payments → orders
│   orders y payments se conectan a NATS para publicar y consumir eventos
```

- Solo el gateway publica un puerto en el host. Los servicios, las bases de datos y NATS solo son accesibles en la red interna de Docker.
- Cada servicio accede únicamente a su propia base de datos.
- Las rutas `/internal/` no se exponen en el gateway.

## Stack tecnológico

| Tecnología | Justificación |
|---|---|
| Python 3.12 + FastAPI + Uvicorn | Python es obligatorio; FastAPI valida datos y genera Swagger automáticamente |
| PostgreSQL 16 (una base de datos por servicio) | Patrón *database-per-service*: cada servicio es dueño de sus datos y no hay acoplamiento por el esquema |
| SQLAlchemy + psycopg | Capa de acceso común a todos los servicios, con transacciones para el descuento atómico de stock |
| HTTP con httpx | Comunicación síncrona cuando hace falta una respuesta inmediata, como la verificación de stock |
| NATS JetStream | Comunicación asíncrona con entrega persistente: un evento no se pierde si el consumidor está caído |
| JWT + bcrypt | Cada servicio valida el token localmente, sin llamar a `users` en cada petición; bcrypt protege las contraseñas |
| Nginx | Punto único de entrada: enruta hacia los servicios, sirve el frontend y oculta las rutas internas |
| HTML + JavaScript vanilla | La interfaz no es el foco del proyecto, así que no necesita framework |
| Docker Compose | Arranca todo el sistema con un solo comando; los *healthchecks* garantizan el orden de arranque |

## Servicios

| Servicio | Responsabilidad | Puerto interno |
|---|---|---|
| `users` | Registro, login, emisión de JWT y perfil de usuario | 8000 |
| `catalog` | Modelos, tallas y stock; descuento atómico de stock | 8000 |
| `orders` | Pedidos y orquestación de la saga de compra | 8000 |
| `payments` | Pagos simulados y publicación de sus eventos | 8000 |
| `users-db`, `catalog-db`, `orders-db`, `payments-db` | PostgreSQL de cada servicio | 5432 |
| `nats` | Mensajería con JetStream | 4222 |
| `gateway` | API Gateway y frontend estático | 80 (8080 en el host) |

Cada servicio corre en su propio contenedor, por eso todos pueden usar el puerto 8000.

## Flujo de compra

El contrato completo está en [docs/api.md](docs/api.md) (en portugués).

1. **Crear el pedido.** El cliente envía `POST /api/orders` con su JWT.
2. **Verificación síncrona de stock.** `orders` llama a `catalog` por HTTP (`GET /products/{id}/availability?size=`) para cada línea. Sin stock, responde `409` y no crea nada. Con stock, el pedido queda en `PENDING_PAYMENT`. El stock aún no queda reservado.
3. **Pago simulado.** El cliente envía `POST /api/payments`. `payments` obtiene el importe de `orders` y rechaza las tarjetas que acaban en `0000`.
4. **Evento de pago.** `payments` publica `payment.confirmed` en NATS. Si la tarjeta se rechaza, publica `payment.failed`, el pedido pasa a `PAYMENT_FAILED` y el flujo termina.
5. **Descuento atómico de stock.** `orders` consume `payment.confirmed`, pasa el pedido a `PAID` y llama a `POST /internal/stock/decrement` en `catalog`. Todas las líneas se descuentan en una sola transacción, y solo si hay stock suficiente.
6. **Pedido confirmado.** El pedido pasa a `CONFIRMED` y `orders` publica `order.confirmed`.

### Compensación (saga)

Entre los pasos 2 y 5 hay una ventana en la que otro cliente puede comprar las últimas unidades. En ese caso, el descuento responde `409` y no cambia nada. Como el pago ya se ha hecho y no hay una transacción distribuida que revertir, la saga compensa: el pedido pasa a `CANCELLED` y el pago se anula con un reembolso simulado.

El mecanismo del reembolso está por decidir; la propuesta está en los [puntos abiertos](docs/api.md#pontos-em-aberto).

## Requisitos previos

- Docker con Docker Compose v2
- Git

No hace falta instalar Python en el host: todo corre dentro de los contenedores.

## Cómo ejecutarlo

```bash
cp .env.example .env
```

```bash
docker compose up --build
```

Cambia los valores de `.env` si el entorno es compartido. El fichero `.env` no se guarda en Git. Si el puerto 8080 está ocupado, cambia `GATEWAY_PORT` en `.env`.

### URLs de acceso

| Qué | URL |
|---|---|
| Frontend | http://localhost:8080/ |
| Salud de `users` | http://localhost:8080/api/users/health |
| Salud de `catalog` | http://localhost:8080/api/catalog/health |
| Salud de `orders` | http://localhost:8080/api/orders/health |
| Salud de `payments` | http://localhost:8080/api/payments/health |

### Swagger de cada servicio

| Servicio | URL |
|---|---|
| `users` | http://localhost:8080/api/users/docs |
| `catalog` | http://localhost:8080/api/catalog/docs |
| `orders` | http://localhost:8080/api/orders/docs |
| `payments` | http://localhost:8080/api/payments/docs |

## Cómo ejecutar los tests

Los tests corren dentro de la imagen de cada servicio, con Python 3.12 y las dependencias correctas:

```bash
docker compose run --rm --no-deps users pytest
```

```bash
docker compose run --rm --no-deps catalog pytest
```

```bash
docker compose run --rm --no-deps orders pytest
```

```bash
docker compose run --rm --no-deps payments pytest
```

Después de cambiar código o tests, añade `--build` para reconstruir la imagen.

## Estructura del repositorio

```
.
├── docker-compose.yml
├── .env.example
├── .gitignore
├── .dockerignore
├── README.md
├── docs/
│   └── api.md              # Contrato de la API, modelos de datos y eventos
├── frontend/
│   ├── index.html
│   └── app.js
├── gateway/
│   └── nginx.conf
├── shared/
│   └── auth/               # Módulo JWT común
└── services/
    └── users | catalog | orders | payments
        ├── Dockerfile
        ├── pytest.ini
        ├── requirements.txt
        ├── app/
        │   ├── main.py
        │   ├── config.py
        │   ├── routes/
        │   ├── models/
        │   ├── schemas/
        │   └── db/
        └── tests/
            └── test_health.py
```

Las imágenes se construyen desde la raíz del repositorio para poder copiar `shared/`.

## Flujo de trabajo en Git

- **`main` protegida:** nadie hace push directo a `main`.
- **Una rama por funcionalidad:** `feat/<servicio>-<descripción>`, por ejemplo `feat/catalog-filtros-productos`.
- **Pull Requests:** cada cambio entra por Pull Request, con revisión de otro miembro del grupo.
- **Commits convencionales:** por ejemplo, `feat: adiciona login`, `fix: corrige desconto de stock`, `docs: atualiza contrato da API`.

## Fechas clave

| Hito | Fecha |
|---|---|
| Entrega (vía e-learning) | 10 de enero de 2027, a las 23:59 |
| Presentación y Prova de Autoria (15 minutos) | Entre el 11 y el 23 de enero de 2027 |
