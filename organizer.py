#!/usr/bin/env python3
"""
Organizador de Downloads - Move arquivos para pastas baseado na extensão.
"""

import os
import shutil
import json
import argparse
import hashlib
import platform
from pathlib import Path
from datetime import datetime

try:
    from plyer import notification
    PLYER_AVAILABLE = True
except ImportError:
    PLYER_AVAILABLE = False

try:
    import send2trash
    SEND2TRASH_AVAILABLE = True
except ImportError:
    SEND2TRASH_AVAILABLE = False


class OrganizadorDownloads:
    def __init__(self, config_file="config.json"):
        with open(config_file, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        self.extensoes = self.config['extensoes']
        self.pastas_ignorar = self.config['pastas_ignorar']
        self.log_file = "organizador_log.json"
        self.historico_movimentacoes = []
        self.modo_silencioso = False

    def _get_pasta_destino(self, extensao):
        extensao = extensao.lower()
        for pasta, extensoes in self.extensoes.items():
            if extensao in extensoes:
                return pasta
        return "Outros"

    def _hash_md5(self, arquivo, limite_kb=1024):
        hash_md5 = hashlib.md5()
        try:
            with open(arquivo, 'rb') as f:
                hash_md5.update(f.read(limite_kb * 1024))
            return hash_md5.hexdigest()
        except (IOError, OSError):
            return None

    def _e_duplicata(self, destino_path, nome_arquivo, hash_original):
        caminho = destino_path / nome_arquivo
        if caminho.exists():
            hash_existente = self._hash_md5(caminho)
            return hash_existente == hash_original
        return False

    def _nome_com_data(self, arquivo):
        data = datetime.fromtimestamp(arquivo.stat().st_mtime).strftime("%Y-%m-%d")
        return f"{data}_{arquivo.name}"

    def _notificar(self, mensagem, titulo="Organizador"):
        if not PLYER_AVAILABLE or self.modo_silencioso:
            return
        try:
            sistema = platform.system()
            if sistema == "Windows":
                notification.notify(title=titulo, message=mensagem, timeout=3)
            elif sistema == "Darwin":
                os.system(f"osascript -e 'display notification \"{mensagem}\" with title \"{titulo}\"'")
            elif sistema == "Linux":
                os.system(f'notify-send "{titulo}" "{mensagem}"')
        except Exception:
            pass

    def _salvar_log(self):
        try:
            with open(self.log_file, 'r') as f:
                historico = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            historico = []

        historico.append({
            "timestamp": datetime.now().isoformat(),
            "arquivos": self.historico_movimentacoes
        })

        if len(historico) > 10:
            historico = historico[-10:]

        with open(self.log_file, 'w') as f:
            json.dump(historico, f, indent=2)

    def organizar(self, pasta, dry_run=False, mover_lixeira=False, adicionar_data=False, quiet=False):
        caminho = Path(pasta)
        self.modo_silencioso = quiet

        if not caminho.exists():
            if not quiet:
                print(f"Erro: Pasta '{pasta}' não encontrada.")
            return

        if not quiet:
            print(f"\nOrganizando: {caminho.absolute()}")
            print("=" * 45)

        if dry_run and not quiet:
            print("Modo simulação - nenhum arquivo será movido\n")

        arquivos = [f for f in caminho.iterdir() if f.is_file()]

        if not arquivos:
            if not quiet:
                print("Nenhum arquivo para organizar.")
            return

        stats = {}

        for arquivo in arquivos:
            extensao = arquivo.suffix
            pasta_destino = self._get_pasta_destino(extensao)
            destino_path = caminho / pasta_destino

            if not dry_run:
                destino_path.mkdir(exist_ok=True)

            if not extensao:
                pasta_destino = "Outros"
                destino_path = caminho / pasta_destino
                if not dry_run:
                    destino_path.mkdir(exist_ok=True)

            nome_arquivo = self._nome_com_data(arquivo) if adicionar_data and not dry_run else arquivo.name

            hash_arquivo = self._hash_md5(arquivo)
            if hash_arquivo and self._e_duplicata(destino_path, nome_arquivo, hash_arquivo):
                if not quiet:
                    print(f"Duplicata ignorada: {arquivo.name}")
                continue

            novo_caminho = destino_path / nome_arquivo
            contador = 1
            while novo_caminho.exists():
                nome_base = Path(nome_arquivo).stem
                ext = Path(nome_arquivo).suffix
                novo_caminho = destino_path / f"{nome_base}_{contador}{ext}"
                contador += 1

            if not quiet:
                print(f"{arquivo.name} → {pasta_destino}/")

            if not dry_run:
                if mover_lixeira and SEND2TRASH_AVAILABLE:
                    send2trash.send2trash(str(arquivo))
                else:
                    shutil.move(str(arquivo), str(novo_caminho))
                    self.historico_movimentacoes.append({
                        "origem": str(arquivo),
                        "destino": str(novo_caminho),
                        "data": datetime.now().isoformat()
                    })
                    stats[pasta_destino] = stats.get(pasta_destino, 0) + 1

        if not dry_run and not mover_lixeira:
            self._salvar_log()
            if not quiet:
                print(f"\nConcluído! {len(arquivos)} arquivos processados.")
                if stats:
                    print("\nPor pasta:")
                    for nome, qtd in sorted(stats.items()):
                        print(f"  {nome}: {qtd} arquivo(s)")
            self._notificar(f"{len(self.historico_movimentacoes)} arquivos organizados")

    def desfazer(self, quiet=False):
        self.modo_silencioso = quiet
        try:
            with open(self.log_file, 'r') as f:
                historico = json.load(f)
        except FileNotFoundError:
            if not quiet:
                print("Nenhum log encontrado.")
            return

        if not historico:
            if not quiet:
                print("Histórico vazio.")
            return

        operacao = historico[-1]

        if not quiet:
            print(f"\nDesfazendo operação de {operacao['timestamp']}")
            print("=" * 45)

        for item in operacao['arquivos']:
            destino = Path(item['destino'])
            origem = Path(item['origem'])

            if destino.exists():
                shutil.move(str(destino), str(origem))
                if not quiet:
                    print(f"Restaurado: {destino.name}")

        if not quiet:
            print("\nOperação desfeita com sucesso.")


def main():
    parser = argparse.ArgumentParser(description="Organizador de Downloads")
    parser.add_argument("pasta", nargs="?", default=str(Path.home() / "Downloads"),
                        help="Pasta a organizar (padrão: Downloads)")
    parser.add_argument("--dry-run", action="store_true", help="Simular sem mover")
    parser.add_argument("--undo", action="store_true", help="Desfazer última organização")
    parser.add_argument("--lixeira", action="store_true", help="Mover para lixeira")
    parser.add_argument("--data", action="store_true", help="Adicionar data ao nome")
    parser.add_argument("--quiet", action="store_true", help="Modo silencioso")

    args = parser.parse_args()

    org = OrganizadorDownloads()

    if args.undo:
        org.desfazer(quiet=args.quiet)
    else:
        org.organizar(
            pasta=args.pasta,
            dry_run=args.dry_run,
            mover_lixeira=args.lixeira,
            adicionar_data=args.data,
            quiet=args.quiet
        )


if __name__ == "__main__":
    main()