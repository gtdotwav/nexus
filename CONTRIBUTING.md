# NEXUS — Guia de Colaboração

## A Regra de Ouro

```
git pull --rebase    ←  SEMPRE antes de começar qualquer coisa
```

Sem exceção. Sem "ah mas eu só vou mudar uma coisinha". **Sempre.**

---

## Workflow: Vibe Coding 24h sem quebrar nada

### O Ciclo (para cada sessão de trabalho)

```
1. git pull --rebase origin main     ← Pega tudo que o outro fez
2. Trabalha nos seus arquivos         ← Foca no seu módulo
3. git add <arquivos>                 ← Adiciona SÓ o que mudou
4. git commit -m "tipo: descrição"    ← Commit com mensagem clara
5. git pull --rebase origin main     ← Pega novidades ANTES de push
6. git push origin main               ← Pusha
```

O passo 5 é o segredo. Se o outro pushou enquanto você trabalhava, o rebase aplica suas mudanças em cima das dele sem conflito.

---

## Divisão de Módulos (Quem mexe no quê)

Para evitar conflitos, cada dev foca em módulos separados:

| Módulo | Diretório | Responsabilidade |
|--------|-----------|-----------------|
| Core | `core/` | Agent, State, EventBus, Consciousness, Foundry, Recovery |
| Brain | `brain/` | Reactive, Strategic, Reasoning |
| Perception | `perception/` | GameReader, ScreenCapture, SpatialMemory |
| Actions | `actions/` | Navigator, Looting, Explorer, Supply, Behaviors |
| Skills | `skills/` | Engine, YAML configs |
| Games | `games/` | Adapters (Tibia, etc.) |
| Dashboard | `dashboard/` | Server, Frontend |
| Scripts | `scripts/` | Installers, Setup |
| Config | `config/` | Settings |

**Regra**: Se dois devs precisam mexer no mesmo arquivo, comunicam antes. Um termina, pusha, o outro faz pull e começa.

---

## Padrão de Commits

Formato: `tipo: descrição curta`

| Tipo | Quando usar |
|------|------------|
| `feat` | Nova funcionalidade |
| `fix` | Correção de bug |
| `perf` | Melhoria de performance |
| `refactor` | Refatoração sem mudar comportamento |
| `docs` | Documentação |
| `test` | Testes |
| `chore` | Manutenção, configs, deps |

Exemplos:
```
feat: add anti-PK flee behavior with threat profiling
fix: reactive brain not resetting combo on target death
perf: spatial memory batch writes reduced from 50ms to 2ms
```

---

## Versionamento

Usamos **Semantic Versioning**: `MAJOR.MINOR.PATCH`

- **PATCH** (0.1.0 → 0.1.1): Bug fix, pequena melhoria
- **MINOR** (0.1.1 → 0.2.0): Nova feature, novo módulo
- **MAJOR** (0.2.0 → 1.0.0): Breaking change, rewrite de sistema

A cada push significativo, o Claude atualiza:
1. `pyproject.toml` → campo `version`
2. `CHANGELOG.md` → nova entrada com data e descrição
3. Badge no `README.md` → versão atualizada

---

## Checklist antes de Push

- [ ] `git pull --rebase origin main` (OBRIGATÓRIO)
- [ ] Código roda sem erro de sintaxe (`python -m py_compile arquivo.py`)
- [ ] Não commitou `config/settings.yaml` (tem API keys)
- [ ] Não commitou `__pycache__/`, `*.db`, `data/`
- [ ] Commit message segue o padrão `tipo: descrição`
- [ ] Se mudou algo significativo, atualizou CHANGELOG

---

## O que NUNCA fazer

1. **`git push --force`** — Destrói o trabalho do outro
2. **Commitar `config/settings.yaml`** — Tem API keys
3. **Mexer em arquivo que o outro está editando** — Comunica antes
4. **Push sem pull** — Vai dar conflito
5. **Commits gigantes** — Quebre em commits menores e focados

---

## Se der conflito

```bash
# Situação: git pull deu conflito
git status                    # Vê quais arquivos conflitaram
# Abre o arquivo, procura por <<<<<<< e resolve manualmente
git add <arquivo_resolvido>
git rebase --continue
git push origin main
```

Na dúvida, comunica com o outro dev antes de resolver.

---

## Setup para novo dev

```bash
git clone https://github.com/gtdotwav/nexus.git
cd nexus
python -m venv venv
source venv/bin/activate
pip install -e ".[all]"
cp config/settings.yaml.example config/settings.yaml
# Edita settings.yaml com sua API key
```

---

*Velocidade máxima. Zero burocracia. Não quebra nada.*
