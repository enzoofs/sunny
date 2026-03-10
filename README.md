# Sunny

Interface visual estilo Netflix para streaming de filmes, series e anime. Agrega metadados do TMDB e Jikan (MyAnimeList), com streaming integrado via multiplos provedores, player no browser (HLS.js) ou mpv local.

> Inspirado no [Luffy](https://github.com/DemonKingSwarn/luffy) por [DemonKingSwarn](https://github.com/DemonKingSwarn) — CLI open-source para streaming de filmes e series. O Sunny nasceu como uma evolucao visual do conceito, adicionando interface grafica estilo Netflix, catalogo com metadados (TMDB/Jikan), streaming no browser via HLS.js, suporte a Chromecast, modo mobile responsivo e acesso remoto via tunnel.

![Python](https://img.shields.io/badge/Python-3.8+-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20macOS%20%7C%20Windows-lightgrey)

## Funcionalidades

- **Catalogo completo** — Filmes, series e anime em uma interface unificada
- **Streaming multi-provedor** — Extrai streams de multiplas fontes em paralelo, usa o primeiro disponivel
- **Player integrado** — HLS.js no browser com controles, Chromecast e compartilhamento
- **Modo desktop** — Janela nativa via pywebview com reprodutor mpv
- **Continuar assistindo** — Historico de reproducao com progresso
- **Responsivo** — Funciona em desktop (ultrawide) e mobile
- **Tunnel remoto** — Acesso externo via cloudflared
- **Legendas** — Suporte a legendas em portugues e ingles
- **Sem dependencias externas** — Backend 100% Python stdlib (sem Flask, sem Django)

## Screenshots

<details>
<summary>Tela inicial</summary>
Hero banner com titulo em destaque, rows de tendencias, generos aleatorios e continuar assistindo.
</details>

<details>
<summary>Aba de Anime</summary>
Filtros por genero (shounen, isekai, romance...), ordenacao por popularidade ou nota.
</details>

## Instalacao

### Um comando (Linux / macOS)

```bash
curl -sL https://raw.githubusercontent.com/enzoofs/sunny/main/install.sh | bash
```

Isso baixa, instala em `~/.local/share/sunny` e cria o comando `sunny`.
Depois e so rodar:

```bash
sunny --server
# Acesse http://localhost:8888
```

### Manual (ou Windows)

```bash
# 1. Clone o repositorio
git clone https://github.com/enzoofs/sunny.git
cd sunny

# 2. Configure a API key do TMDB (gratuita)
cp .env.example .env
# Edite .env com sua chave: https://www.themoviedb.org/settings/api

# 3. Rode
python3 server.py --server
# Acesse http://localhost:8888
```

## Acesso mobile

Ao rodar `sunny --server`, o terminal mostra um **QR code** — escaneie com o celular para abrir direto no browser. Os dois dispositivos precisam estar na mesma rede WiFi.

```
  ╔═══════════════════════════════════╗
  ║          Sunny rodando!           ║
  ╚═══════════════════════════════════╝

  Local:    http://localhost:8888
  Rede:     http://192.168.1.42:8888

  ██ █ ██ ██    ← QR code aqui
  █ ██ █ █ █
  ...

  Escaneie o QR code acima com o celular
```

Para acesso fora da rede local (ex: compartilhar com alguem):
```bash
sunny --server --tunnel
# Gera uma URL publica temporaria via cloudflared
```

## Modos de uso

| Flag | Descricao |
|------|-----------|
| (nenhuma) | Abre janela desktop com pywebview |
| `--server` | Roda como servidor HTTP em `0.0.0.0:8888` |
| `--server --tunnel` | Servidor + tunnel cloudflared para acesso externo |
| `--debug` | Habilita logs HTTP verbosos |

```bash
# Porta customizada
PORT=9000 sunny --server
```

## Configuracao

A API key do TMDB pode ser configurada de duas formas (env var tem prioridade):

1. **Variavel de ambiente:** `export TMDB_API_KEY=sua_chave`
2. **Interface:** Ao abrir sem chave, um modal pede a key (salva em `config.json`)

### Dependencias

**Obrigatorias:** Python 3.8+ (sem pacotes externos para o modo servidor)

**Opcionais:**
| Pacote | Para que serve |
|--------|---------------|
| `pywebview` | Modo desktop (janela nativa) |
| `mpv` | Reprodutor de video local |
| `cloudflared` | Tunnel para acesso remoto |

```bash
# Instalar opcionais (Arch Linux)
sudo pacman -S mpv cloudflared
pip install pywebview
```

## Arquitetura

```
Sunny
├── server.py                  # Servidor HTTP, API endpoints, proxy HLS
├── provider/                  # Pipeline de extracao de streams
│   ├── __init__.py            # Orquestra busca → selecao → extracao
│   ├── flixhq.py             # Scraping FlixHQ (busca, temporadas, episodios)
│   ├── embeds.py              # Provedores rapidos via TMDB ID (autoembed, 2embed)
│   ├── decrypt.py             # Decryption de streams (megacloud, embed.su, generico)
│   └── http.py                # Helpers HTTP
├── static/                    # Frontend
│   ├── index.html             # Shell da aplicacao
│   ├── app.js                 # Logica frontend (vanilla JS)
│   └── style.css              # Estilos (tema escuro Netflix-like)
├── tests/                     # Testes unitarios
│   ├── test_flixhq.py        # Testes do scraper FlixHQ
│   ├── test_decrypt.py        # Testes de decryption
│   └── test_server.py         # Testes do servidor
├── fake-mpv/                  # Utilitario de teste (mpv mock)
├── .env.example               # Template de variaveis de ambiente
└── .gitignore
```

### Como o streaming funciona

```
Usuario clica "Play"
       │
       ▼
  POST /api/stream {title, season, episode, tmdb_id}
       │
       ├─── Embed providers (rapido, ~2-3s) ──── autoembed.cc / 2embed.cc
       │         │                                       │
       │         ▼                                       ▼
       │    Busca player URL ──────────────── decrypt_stream()
       │                                           │
       ├─── FlixHQ (fallback, ~15s) ──── search → select → extract
       │         │                              │
       │         ▼                              ▼
       │    get_servers() → get_link() ── decrypt_stream()
       │
       ▼
  Primeiro provedor que retorna ───► Proxy HLS reescreve URLs
                                           │
                                           ▼
                                     Player HLS.js no browser
```

Os provedores correm em paralelo — o primeiro a retornar um stream valido ganha.

### Decryption suportada

| Provedor | Metodo |
|----------|--------|
| Megacloud / RabbitStream | Algoritmo 3 camadas (seed shift + columnar + substitution) |
| Embed.su | Hash base64 duplo com reversao |
| Generico | Regex para extrair URLs m3u8 do HTML |

### Cache

| Recurso | TTL | Motivo |
|---------|-----|--------|
| Info de midia (FlixHQ) | 30 min | Evitar re-scraping |
| Resultados de busca | 10 min | Reduzir requests |
| Chave megacloud | 10 min | Chave muda periodicamente |
| API Jikan | 5 min | Rate limit do MAL |
| Titulos indisponiveis | 24 horas | Nao tentar extrair de novo |

## API Endpoints

### Descoberta de conteudo

| Rota | Metodo | Descricao |
|------|--------|-----------|
| `/api/search?q=&type=` | GET | Busca multi-tipo (multi, tv, movie) |
| `/api/trending?type=&window=` | GET | Tendencias (dia/semana) |
| `/api/discover?type=&genre=&sort=` | GET | Descoberta avancada com filtros |
| `/api/details?type=&id=` | GET | Detalhes completos + temporadas |
| `/api/season?id=&season=` | GET | Episodios de uma temporada |
| `/api/genres?type=` | GET | Lista de generos |

### Anime (Jikan/MAL)

| Rota | Metodo | Descricao |
|------|--------|-----------|
| `/api/anime/categories` | GET | 28 generos/demografias |
| `/api/anime/top?filter=` | GET | Top anime por popularidade ou nota |
| `/api/anime/season?year=&season=` | GET | Anime da temporada |
| `/api/anime/genre?genre=&order_by=` | GET | Anime por genero |
| `/api/anime/search?q=` | GET | Busca de anime |
| `/api/anime/details?id=` | GET | Detalhes completos |

### Streaming e reproducao

| Rota | Metodo | Descricao |
|------|--------|-----------|
| `/api/play` | POST | Extrai stream e abre no mpv (desktop) |
| `/api/stream` | POST | Extrai stream e retorna proxy URL (browser) |
| `/api/proxy/{id}/master.m3u8` | GET | Playlist HLS com URLs reescritas |
| `/api/proxy/{id}/url/{url}` | GET | Proxy de segmentos com headers corretos |

### Historico

| Rota | Metodo | Descricao |
|------|--------|-----------|
| `/api/history` | GET | Ultimo episodio por titulo |
| `/api/history?title=` | GET | Historico completo de um titulo |
| `/api/history?title=` | DELETE | Remover titulo do historico |

### Configuracao

| Rota | Metodo | Descricao |
|------|--------|-----------|
| `/api/config` | GET | Verificar se tem API key |
| `/api/config` | POST | Salvar configuracoes |

## Testes

```bash
# Rodar todos os testes
python3 -m unittest discover -s tests -v

# Rodar teste especifico
python3 -m unittest tests.test_decrypt -v
```

## Atalhos de teclado

| Tecla | Acao |
|-------|------|
| `/` | Focar campo de busca |
| `Esc` | Fechar modal aberto |

## Stack tecnica

**Backend:** Python 3 stdlib (`http.server`, `urllib`, `json`, `re`, `sqlite3`, `threading`)
**Frontend:** HTML5 + CSS3 + Vanilla JavaScript
**Bibliotecas externas:** HLS.js (player), Google Cast SDK (Chromecast)
**APIs:** TMDB, Jikan (MyAnimeList)

## Licenca

MIT

---

Desenvolvido por [Enzo Fernandes](https://github.com/enzoofs)
