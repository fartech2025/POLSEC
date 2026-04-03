# Requisitos Funcionais — Sistema Patrimonial EMTEL

Data: 02/04/2026
Versão: 1.0

---

## RF01 — Autenticação e Controle de Acesso
- O sistema deve exigir login com e-mail e senha
- Deve suportar múltiplos perfis de usuário (administrador, operador, visualizador)
- Cada usuário deve ter permissões configuráveis por módulo

## RF02 — Cadastro de Patrimônio
- Cadastrar bens com: código, descrição, categoria, setor, localização, responsável, data de aquisição, valor
- Editar e inativar bens cadastrados
- Status do bem: Ativo | Em Manutenção | Baixado | Extraviado

## RF03 — Movimentação de Bens
- Registrar transferência de bem entre setores
- Registrar troca de responsável
- Todo movimento deve gerar registro com data, usuário e motivo

## RF04 — Histórico e Rastreabilidade
- Cada bem deve ter histórico completo de alterações
- Registrar: o que mudou, quando mudou, quem mudou

## RF05 — Dashboard Gerencial
- Exibir total de ativos cadastrados
- Distribuição de bens por setor e por status
- Indicadores de bens em manutenção, baixados e extraviados
- Atualização em tempo real

## RF06 — Busca e Filtros
- Busca por código, descrição ou responsável
- Filtros por: setor, status, categoria, localização, período

## RF07 — Auditoria
- Registro automático de todas as ações do sistema (audit log)
- Log deve conter: usuário, ação, data/hora, registro afetado
- Exportação de log para relatório

---

## Requisitos Não Funcionais

| RNF | Descrição |
|-----|-----------|
| RNF01 | Sistema acessível via navegador (Chrome, Firefox, Edge, Safari) |
| RNF02 | Interface responsiva (desktop e mobile) |
| RNF03 | Tempo de resposta inferior a 2 segundos nas operações comuns |
| RNF04 | Dados armazenados com backup automático |
| RNF05 | Acesso via HTTPS (comunicação criptografada) |
| RNF06 | Suporte a múltiplos usuários simultâneos |
