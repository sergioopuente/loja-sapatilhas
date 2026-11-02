# Módulo JWT comum

Aqui ficará o módulo JWT partilhado por todos os serviços: validação local dos tokens emitidos por `users` e extração da identidade e do papel do utilizador.

**Responsável:** Gustavo

As imagens Docker são construídas a partir da raiz do repositório e copiam `shared/` para `/code/shared`, pelo que o módulo poderá ser importado como `shared.auth`.
