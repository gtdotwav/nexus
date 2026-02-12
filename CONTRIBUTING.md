# NEXUS — Guia de Colaboração (v0.2.0)

## A Regra de Ouro

```
git pull --rebase origin main    ←  SEMPRE antes de começar qualquer coisa
```

Sem exceção. Sem "ah mas eu só vou mudar uma coisinha". **Sempre.**

---

## Setup (cada dev faz uma vez)

```bash
git clone https://github.com/gtdotwav/nexus.git
cd nexus
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -e ".[all]"
cp config/settings.yaml.example config/settings.yaml
# Edita settings.yaml com sua API key

# INSTALA OS HOOKS DE PROTEÇÃO (obrigatório)
bash scripts/install_hooks.sh
```

Os hooks bloqueiam automaticamente:
- Push com erro de sintaxe
- Push com API keys no código
- Commit do `config/settings.yaml`
- Commit com `breakpoint()` / `import pdb`

---

## Arquitetura v0.2.0 — Como funciona a divisão

### Cada dev trabalha em arquivos diferentes, sem conflito:

```
Dev A → core/loops/strategic.py + brain/strategic.py
Dev B → core/loops/perception.py + perception/game_reader_v2.py
Dev C → core/loops/action.py + actions/navigator.py
```

### Os 3 pontos de extensão "zero-conflito":

| Quer adicionar...    | Arquivo a criar/editar                 | NÃO toca em...     |
|----------------------|----------------------------------------|---------------------|
| Novo loop            | `core/loops/meu_loop.py`              | `core/agent.py`     |
| Novo modelo de dados | `core/state/models.py`                 | `game_state.py`     |
| Nova skill YAML      | `skills/tibia/minha_skill.yaml`        | `skills/engine.py`  |

---

## Workflow: Vibe Coding 24h

### O Ciclo (para cada sessão de trabalho)

```
1. git pull --rebase origin main     ← Pega tudo que o outro fez
2. Lê o git log recente              ← Entende o que mudou
3. Trabalha nos seus módulos          ← NÃO toca no que o outro está mexendo
4. git add <arquivos específicos>     ← Adiciona SÓ o que mudou
5. git commit -m "tipo: descrição"    ← Commit com mensagem clara
6. git pull --rebase origin main     ← Pega novidades ANTES de push
7. git push origin main               ← Pusha
```

O passo 6 é o segredo. Se o outro pushou enquanto você trabalhava, o rebase aplica suas mudanças em cima das dele sem conflito.

---

## Os 6 Modos de Falha (e como evitar cada um)

### 1. Import Quebrado

**Cenário**: Dev A renomeia função em `core/state/game_state.py`. Dev B usa a função antiga. Main quebra.

**Proteção**: O CI roda `import` de todos os 37 módulos em cada push. Se qualquer import falhar, o push é marcado como falho no GitHub.

**Prevenção**: Antes de renomear qualquer coisa, busca quem usa:
```bash
grep -r "nome_da_funcao" --include="*.py" .
```

### 2. Push Simultâneo

**Cenário**: Ambos editam o mesmo arquivo, ambos tentam push.

**Proteção**: `git pull --rebase` no passo 6 resolve automaticamente se as mudanças estão em linhas diferentes. Se estão nas mesmas linhas, git para e pede pra resolver manualmente.

**Prevenção**: Dividam por módulo. Não editem o mesmo arquivo ao mesmo tempo.

### 3. Secret Leak

**Cenário**: Alguém commita uma API key no código.

**Proteção tripla**:
- Pre-commit hook bloqueia `config/settings.yaml`
- Pre-push hook bloqueia `sk-ant-` e `ghp_` em qualquer arquivo
- CI verifica no GitHub como última linha de defesa

### 4. GameState Quebrado (O Ponto Crítico)

**Cenário**: Alguém muda `core/state/game_state.py` e quebra 13 arquivos que dependem dele.

**Realidade arquitetural**: `GameState` é importado por 13 dos 51 arquivos Python. É o ponto de falha número 1 do sistema.

**Regra**: Mudanças em `core/state/game_state.py` exigem:
1. Buscar TODOS os importadores: `grep -r "from core.state" --include="*.py" .`
2. Verificar compatibilidade
3. Rodar: `python -c "import core.agent"` (importa tudo recursivamente)
4. Só então commitar

**Nota**: Adicionar novos enums em `core/state/enums.py` ou novos modelos em `core/state/models.py` é seguro — não quebra nada.

### 5. Force Push

**Cenário**: Alguém faz `git push --force` e apaga o trabalho do outro.

**Proteção**: Configura branch protection no GitHub (Settings → Branches → Add rule → main → "Disallow force pushes").

### 6. Context Drift (IA sem contexto)

**Cenário**: O Claude do Dev A não sabe o que o Claude do Dev B fez. Cria código duplicado ou incompatível.

**Proteção**: `CLAUDE.md` na raiz do repo — lido automaticamente pelo Claude no início de cada sessão.

**Prevenção adicional**: Toda sessão de IA começa com:
```bash
git pull --rebase origin main
git log --oneline -10            # Últimos 10 commits
git diff HEAD~3 --stat           # O que mudou nos últimos 3 commits
```

---

## Mapa de Dependências (Quem quebra quem)

```
core/state/game_state.py (GameState)  ←  13 arquivos dependem
├── actions/behaviors.py
├── actions/explorer.py
├── actions/looting.py
├── actions/navigator.py
├── actions/supply_manager.py
├── brain/reactive.py
├── brain/reasoning.py
├── perception/game_reader.py
├── perception/game_reader_v2.py
├── core/agent.py
├── core/recovery.py
├── skills/engine.py
└── games/tibia/adapter.py

⚠️  MEXEU NO GameState → VERIFICA TODOS ESSES ARQUIVOS
ℹ️  enums.py e models.py são SEGUROS — mudanças não propagam
```

---

## Divisão de Módulos

Para evitar conflitos, cada dev foca em módulos separados:

| Módulo | Diretório | Arquivos |
|--------|-----------|----------|
| Core Agent | `core/` | agent.py, consciousness.py, event_bus.py, foundry.py, recovery.py |
| State | `core/state/` | enums.py, models.py, game_state.py |
| Loops | `core/loops/` | perception, reactive, action, strategic, consciousness, evolution, recovery, reasoning, metrics |
| Brain | `brain/` | reactive.py, strategic.py, reasoning.py |
| Perception | `perception/` | game_reader_v2.py, screen_capture.py, spatial_memory_v2.py |
| Actions | `actions/` | navigator.py, looting.py, explorer.py, supply_manager.py, behaviors.py |
| Skills | `skills/` | engine.py, tibia/ (YAML configs) |
| Games | `games/` | base.py, registry.py, tibia/adapter.py |
| Dashboard | `dashboard/` | server.py, app.html |

**Regra**: Se dois devs precisam mexer no mesmo arquivo, comunica antes. Um termina, pusha, o outro faz pull e começa.

---

## Como Adicionar um Novo Loop (Exemplo)

Suponha que você quer adicionar um loop de "anti-AFK" que mexe o mouse periodicamente:

**1. Crie o arquivo** `core/loops/anti_afk.py`:

```python
"""NEXUS — Anti-AFK Loop"""
from __future__ import annotations
import structlog
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.agent import NexusAgent

log = structlog.get_logger()

async def run(agent: NexusAgent) -> None:
    """Micro-movements to avoid AFK kick."""
    import asyncio
    while agent.running:
        try:
            # Sua lógica aqui
            pass
        except Exception as e:
            log.error("anti_afk.error", error=str(e))
        await asyncio.sleep(30)
```

**2. Registre em** `core/loops/__init__.py`:

```python
from core.loops.anti_afk import run as anti_afk_loop
# Adicione na lista ALL_LOOPS:
("anti_afk", anti_afk_loop),
```

**3. Commit e push.** Pronto — o loop roda automaticamente.

---

## Padrão de Commits

Formato: `tipo: descrição curta em inglês`

| Tipo | Quando usar |
|------|------------|
| `feat` | Nova funcionalidade |
| `fix` | Correção de bug |
| `perf` | Melhoria de performance |
| `refactor` | Refatoração sem mudar comportamento |
| `docs` | Documentação |
| `test` | Testes |
| `chore` | Manutenção, configs, deps |

---

## Versionamento

**Semantic Versioning**: `MAJOR.MINOR.PATCH`

- **PATCH** (0.2.0 → 0.2.1): Bug fix, pequena melhoria
- **MINOR** (0.2.0 → 0.3.0): Nova feature, novo módulo
- **MAJOR** (0.2.0 → 1.0.0): Breaking change, rewrite de sistema

Para bumpar versão:
```bash
python scripts/bump_version.py patch    # ou minor / major
# Edita CHANGELOG.md com a descrição real
git add pyproject.toml README.md CHANGELOG.md
git commit -m "chore: bump version to X.Y.Z"
git push origin main
```

---

## O que NUNCA fazer

1. **`git push --force`** — Destrói o trabalho do outro
2. **Commitar `config/settings.yaml`** — Tem API keys
3. **Mexer em `core/state/game_state.py` sem verificar os 13 dependentes**
4. **Push sem pull** — Vai dar conflito
5. **Commits gigantes** — Quebre em commits menores e focados
6. **Ignorar CI vermelho** — Se o CI falhou, algo está quebrado
7. **Editar `core/agent.py` sem necessidade** — Para adicionar loops, use `core/loops/`

---

## Se der conflito

```bash
git status                    # Vê quais arquivos conflitaram
# Abre o arquivo, procura por <<<<<<< e resolve
git add <arquivo_resolvido>
git rebase --continue
git push origin main
```

Na dúvida, comunica com o outro dev antes de resolver.

---

## Proteções Automáticas

| Camada | O que faz | Quando roda |
|--------|----------|-------------|
| **pre-commit hook** | Bloqueia settings.yaml e breakpoints | Antes de cada commit |
| **pre-push hook** | Bloqueia syntax errors e secrets | Antes de cada push |
| **GitHub Actions CI** | Syntax + 37 imports + secrets + version check | Em cada push na main |

As 3 camadas juntas garantem que código quebrado **nunca** chega na main.

---

*Velocidade máxima. Zero burocracia. Três camadas de proteção.*
