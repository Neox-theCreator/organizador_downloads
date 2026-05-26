#!/usr/bin/env python3
"""
Organizador de Downloads - Move arquivos para pastas baseado na extensão.
Autor: Seu Nome
GitHub: https://github.com/seuusuario/organizador-downloads
"""

import os
import shutil
import json
import argparse
from pathlib import Path
from datetime import datetime


class OrganizadorDownloads:
    def __init__(self, config_file="config.json"):
        """Carrega as configurações do arquivo JSON"""
        with open(config_file, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        self.extensoes = self.config['extensoes']
        self.pastas_ignorar = self.config['pastas_ignorar']
        self.arquivos_movidos = []  # Para registrar para possível undo
        self.log_file = "organizador_log.json"

    def obter_pasta_destino(self, extensao):
        """Retorna qual pasta deve receber o arquivo baseado na extensão"""
        extensao = extensao.lower()
        for pasta, extensoes in self.extensoes.items():
            if extensao in extensoes:
                return pasta
        return "Outros"  # Se não encontrou nenhuma categoria

    def organizar(self, caminho_pasta, dry_run=False, mover_para_lixeira=False):
        """
        Organiza os arquivos da pasta especificada.
        dry_run: apenas mostra o que seria feito, não move nada
        """
        caminho = Path(caminho_pasta)

        if not caminho.exists():
            print(f"❌ Erro: A pasta '{caminho_pasta}' não existe!")
            return

        print(f"\n📂 Organizando: {caminho.absolute()}")
        print("=" * 50)

        if dry_run:
            print("🔍 [MODO SIMULAÇÃO] - Nenhum arquivo será movido\n")

        arquivos = [f for f in caminho.iterdir() if f.is_file()]

        if not arquivos:
            print("✅ Nenhum arquivo para organizar!")
            return

        for arquivo in arquivos:
            extensao = arquivo.suffix
            destino_pasta = self.obter_pasta_destino(extensao)
            destino_path = caminho / destino_pasta

            # Criar pasta de destino se não existir
            if not dry_run:
                destino_path.mkdir(exist_ok=True)

            # Tratar arquivos sem extensão
            if not extensao:
                destino_pasta = "Outros"
                destino_path = caminho / destino_pasta
                if not dry_run:
                    destino_path.mkdir(exist_ok=True)

            novo_caminho = destino_path / arquivo.name

            # Verificar se já existe arquivo com mesmo nome
            if novo_caminho.exists():
                nome_base = arquivo.stem
                contador = 1
                while novo_caminho.exists():
                    novo_nome = f"{nome_base}_{contador}{extensao}"
                    novo_caminho = destino_path / novo_nome
                    contador += 1

            print(f"📄 {arquivo.name} → {destino_pasta}/")

            if not dry_run:
                shutil.move(str(arquivo), str(novo_caminho))
                self.arquivos_movidos.append({
                    "origem": str(arquivo),
                    "destino": str(novo_caminho),
                    "data": datetime.now().isoformat()
                })

        if not dry_run:
            self._salvar_log()
            print(f"\n✅ Organização concluída! {len(arquivos)} arquivos organizados.")
            print(f"📝 Log salvo em: {self.log_file}")
        else:
            print(f"\n🔍 Simulação concluída! {len(arquivos)} arquivos seriam movidos.")

    def _salvar_log(self):
        """Salva log das operações para possível undo"""
        try:
            with open(self.log_file, 'r') as f:
                historico = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            historico = []

        historico.append({
            "timestamp": datetime.now().isoformat(),
            "arquivos": self.arquivos_movidos
        })

        with open(self.log_file, 'w') as f:
            json.dump(historico, f, indent=2)

    def desfazer(self, num_operacao=-1):
        """Desfaz a última organização (ou uma específica)"""
        try:
            with open(self.log_file, 'r') as f:
                historico = json.load(f)
        except FileNotFoundError:
            print("❌ Nenhum log encontrado. Nada para desfazer.")
            return

        if not historico:
            print("❌ Histórico vazio.")
            return

        if num_operacao == -1:
            operacao = historico[-1]  # Última
        else:
            if num_operacao >= len(historico):
                print(f"❌ Operação {num_operacao} não existe. Total: {len(historico)}")
                return
            operacao = historico[num_operacao]

        print(f"\n↩️ Desfazendo operação de {operacao['timestamp']}")
        print("=" * 50)

        for item in operacao['arquivos']:
            destino = Path(item['destino'])
            origem_original = Path(item['origem'])

            if destino.exists():
                shutil.move(str(destino), str(origem_original))
                print(f"↩️ {destino.name} → {origem_original.parent}")
            else:
                print(f"⚠️ Arquivo não encontrado: {destino.name}")

        print("\n✅ Desfeito com sucesso!")


def main():
    parser = argparse.ArgumentParser(
        description="Organizador de Downloads - Move arquivos para pastas por extensão",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  %(prog)s                    # Organiza a pasta Downloads padrão
  %(prog)s ~/Downloads        # Organiza uma pasta específica
  %(prog)s --dry-run          # Simulação (não move nada)
  %(prog)s --undo             # Desfaz a última organização
        """
    )

    parser.add_argument(
        "pasta",
        nargs="?",
        default=str(Path.home() / "Downloads"),
        help="Pasta a organizar (padrão: ~/Downloads)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Apenas simula, não move arquivos"
    )

    parser.add_argument(
        "--undo",
        action="store_true",
        help="Desfaz a última organização"
    )

    parser.add_argument(
        "--lixeira",
        action="store_true",
        help="(opcional) Move para lixeira ao invés de organizar"
    )

    args = parser.parse_args()

    organizador = OrganizadorDownloads()

    if args.undo:
        organizador.desfazer()
    else:
        organizador.organizar(args.pasta, dry_run=args.dry_run, mover_para_lixeira=args.lixeira)


if __name__ == "__main__":
    main()