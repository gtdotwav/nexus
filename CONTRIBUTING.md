# NEXUS — Guia de Colaboração

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

**Cenário**: Dev A renomeia uma função em `core/state.py`. Dev B usa a função antiga. Main quebra.

**Proteção**: O CI roda `import` de todos os 24 módulos em cada push. Se qualquer import falhar, o push é marcado como falho no GitHub.

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

**Cenário**: Alguém muda `core/state.py` e quebra 13 arquivos que dependem dele.

**Realidade arquitetural**: `GameState` é importado por 13 dos 38 arquivos Python. É o ponto de falha número 1 do sistema.

**Regra**: Mudanças em `core/state.py` exigem:
1. Buscar TODOS os importadores: `grep -r "from core.state\|from core import" --include="*.py" .`
2. Atualizar todos eles
3. Rodar: `python -c "import core.agent"` (importa tudo recursivamente)
4. Só então commitar

### 5. Force Push

**Cenário**: Alguém faz `git push --force` e apaga o trabalho do outro.

**Proteção**: Configura branch protection no GitHub (Settings → Branches → Add rule → main → "Disallow force pushes").

### 6. Context Drift (IA sem contexto)

**Cenário**: O Claude do Dev A não sabe o que o Claude do Dev B fez. Cria código duplicado ou incompatível.

**Prevenção**: Toda sessão de IA começa com:
```bash
git pull --rebase origin main
git log --oneline -10            # Últimos 10 commits
git diff HEAD~3 --stat           # O que mudou nos últimos 3 commits
```
Isso dá ao Claude o contexto do que o outro dev fez.

---

## Mapa de Dependências (Quem quebra quem)

```
core/state.py (GameState)  ←  13 arquivos dependem
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
```

---

## Divisão de Módulos

Para evitar conflitos, cada dev foca em módulos separados:

| Módulo | Diretório | Arquivos |
|--------|-----------|----------|
| Core | `core/` | agent, state, event_bus, consciousness, foundry, recovery |
| Brain | `brain/` | reactive, strategic, reasoning |
| Perception | `perception/` | game_reader*, screen_capture, spatial_memory* |
| Actions | `actions/` | navigator, looting, explorer, supply_manager, behaviors |
| Skills | `skills/` | engine, YAML configs |
| Games | `games/` | base, registry, tibia/adapter |
| Dashboard | `dashboard/` | server, app.html |

**Regra**: Se dois devs precisam mexer no mesmo arquivo, comunica antes. Um termina, pusha, o outro faz pull e começa.

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

- **PATCH** (0.1.0 → 0.1.1): Bug fix, pequena melhoria
- **MINOR** (0.1.1 → 0.2.0): Nova feature, novo módulo
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
3. **Mexer em `core/state.py` sem verificar os 13 dependentes**
4. **Push sem pull** — Vai dar conflito
5. **Commits gigantes** — Quebre em commits menores e focados
6. **Ignorar CI vermelho** — Se o CI falhou, algo está quebrado

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
| **GitHub Actions CI** | Syntax + imports + secrets + version check | Em cada push na main |

As 3 camadas juntas garantem que código quebrado **nunca** chega na main.

---

*Velocidade máxima. Zero burocracia. Três camadas de proteção.*
