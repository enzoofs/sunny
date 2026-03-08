#!/usr/bin/env bash
# Sunny — Instalador automatico
# Uso: curl -sL https://raw.githubusercontent.com/enzoofs/sunny/main/install.sh | bash

set -e

REPO="enzoofs/sunny"
INSTALL_DIR="$HOME/.local/share/sunny"
BIN_DIR="$HOME/.local/bin"

echo ""
echo "  ╔═══════════════════════════╗"
echo "  ║     Instalando Sunny      ║"
echo "  ╚═══════════════════════════╝"
echo ""

# Verificar Python 3
if ! command -v python3 &>/dev/null; then
    echo "ERRO: Python 3 nao encontrado. Instale antes de continuar."
    echo "  Arch:   sudo pacman -S python"
    echo "  Ubuntu: sudo apt install python3"
    echo "  macOS:  brew install python3"
    exit 1
fi

PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "[+] Python $PY_VERSION encontrado"

# Criar diretorios
mkdir -p "$INSTALL_DIR" "$BIN_DIR"

# Baixar ultima versao
echo "[+] Baixando Sunny..."
if command -v curl &>/dev/null; then
    curl -sL "https://github.com/$REPO/archive/refs/heads/main.tar.gz" -o /tmp/sunny.tar.gz
elif command -v wget &>/dev/null; then
    wget -q "https://github.com/$REPO/archive/refs/heads/main.tar.gz" -O /tmp/sunny.tar.gz
else
    echo "ERRO: curl ou wget necessario."
    exit 1
fi

# Extrair
echo "[+] Extraindo..."
rm -rf "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
tar -xzf /tmp/sunny.tar.gz -C "$INSTALL_DIR" --strip-components=1
rm /tmp/sunny.tar.gz

# Criar launcher
cat > "$BIN_DIR/sunny" << 'LAUNCHER'
#!/usr/bin/env bash
SUNNY_DIR="$HOME/.local/share/sunny"

# Passar argumentos (--server, --tunnel, --debug)
cd "$SUNNY_DIR"
exec python3 server.py "$@"
LAUNCHER
chmod +x "$BIN_DIR/sunny"

# Verificar se ~/.local/bin esta no PATH
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo ""
    echo "[!] Adicione ~/.local/bin ao seu PATH:"
    if [[ "$SHELL" == *"zsh"* ]]; then
        echo '    echo '\''export PATH="$HOME/.local/bin:$PATH"'\'' >> ~/.zshrc && source ~/.zshrc'
    else
        echo '    echo '\''export PATH="$HOME/.local/bin:$PATH"'\'' >> ~/.bashrc && source ~/.bashrc'
    fi
fi

# Configurar TMDB key se nao existe
if [ ! -f "$INSTALL_DIR/config.json" ] || ! grep -q "tmdb_api_key" "$INSTALL_DIR/config.json" 2>/dev/null; then
    echo ""
    echo "[?] Voce precisa de uma API key do TMDB (gratuita)."
    echo "    Pegue em: https://www.themoviedb.org/settings/api"
    echo ""
    read -rp "    Cole sua TMDB API key (ou Enter pra configurar depois): " TMDB_KEY
    if [ -n "$TMDB_KEY" ]; then
        echo "{\"tmdb_api_key\": \"$TMDB_KEY\"}" > "$INSTALL_DIR/config.json"
        echo "[+] API key salva!"
    else
        echo "[*] Sem problema — configure pela interface ao abrir o Sunny."
    fi
fi

echo ""
echo "  Instalacao concluida!"
echo ""
echo "  Como usar:"
echo "    sunny --server        Abre no browser (http://localhost:8888)"
echo "    sunny                 Abre janela desktop (requer pywebview)"
echo "    sunny --server --tunnel   Acesso externo via tunnel"
echo ""
echo "  Para desinstalar:"
echo "    rm -rf ~/.local/share/sunny ~/.local/bin/sunny"
echo ""
