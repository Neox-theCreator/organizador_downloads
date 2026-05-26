#!/usr/bin/env python3
"""
Organizador de Downloads - Move arquivos para pastas baseado na extensão.
Autor: Neox-theCreator
GitHub: https://github.com/Neox-theCreator/organizador-downloads
"""

import os
import shutil
import json
import argparse
import hashlib
import platform
from pathlib import Path
from datetime import datetime

# Tentar importar send2trash (opcional)
try:
    import send2trash

    SEND2TRASH_AVAILABLE = True
except ImportError:
    SEND2TRASH_AVAILABLE = False
    print("💡 Dica: Instale 'send2trash' para mover para lixeira: pip install send2trash")

# Tentar importar plyer para notificações (opcional)
try:
    from plyer import notification

    PLYER_AVAILABLE = True
except ImportError:
    PLYER_AVAILABLE = False
    print("💡 Dica: Instale 'plyer' para notificações: pip install plyer")


class OrganizadorDownloads:
    def __init__(self, config_file="config.json"):
        """Carrega as configurações do arquivo JSON"""
        with open(config_file, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        self.extensoes = self.config['extensoes']
        self.pastas_ignorar = self.config['pastas_ignorar']
        self.arquivos_movidos = []  # Para registrar para possível undo
        self.log_file = "organizador_log.json"
        self.quiet = False  # Modo silencioso
        self.estatisticas = {}  # Contador por pasta

    def obter_pasta_destino(self, extensao):
        """Retorna qual pasta deve receber o arquivo baseado na extensão"""
        extensao = extensao.lower()
        for pasta, extensoes in self.extensoes.items():
            if extensao in extensoes:
                return pasta
        return "Outros"  # Se não encontrou nenhuma categoria

    def _calcular_hash_md5(self, arquivo, primeiros_kb=1024):
        """Calcula hash MD5 dos primeiros N KB para detectar duplicatas rapidamente"""
        hash_md5 = hashlib.md5()
        try:
            with open(arquivo, 'rb') as f:
                # Lê apenas os primeiros KB para performance
                chunk = f.read(primeiros_kb * 1024)
                hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except (IOError, OSError):
            return None

    def _verificar_duplicata(self, destino_path, nome_arquivo, hash_original):
        """Verifica se já existe arquivo com mesmo nome e mesmo conteúdo"""
        caminho_completo = destino_path / nome_arquivo
        if caminho_completo.exists():
            # Se tem o mesmo nome, verifica hash
            hash_existente = self._calcular_hash_md5(caminho_completo)
            if hash_existente == hash_original:
                return True  # É duplicata exata
        return False

    def _nome_com_data(self, arquivo):
        """Adiciona data de modificação ao nome do arquivo (opcional)"""
        data_mod = datetime.fromtimestamp(arquivo.stat().st_mtime).strftime("%Y-%m-%d")
        nome_base = arquivo.stem
        extensao = arquivo.suffix
        return f"{data_mod}_{nome_base}{extensao}"

    def _notificar(self, mensagem, titulo="Organizador de Downloads"):
        """Envia notificação do sistema (opcional)"""
        if not PLYER_AVAILABLE:
            return

        sistema = platform.system()
        try:
            if sistema == "Windows":
                notification.notify(
                    title=titulo,
                    message=mensagem,
                    timeout=5
                )
            elif sistema == "Darwin":  # macOS
                os.system(f"osascript -e 'display notification \"{mensagem}\" with title \"{titulo}\"'")
            elif sistema == "Linux":
                os.system(f'notify-send "{titulo}" "{mensagem}"')
        except Exception:
            pass  # Falha na notificação não quebra o programa

    def _contar_arquivos_por_pasta(self):
        """Conta quantos arquivos foram para cada pasta"""
        stats = {}
        for item in self.arquivos_movidos:
            pasta = Path(item['destino']).parent.name
            stats[pasta] = stats.get(pasta, 0) + 1
        return stats

    def organizar(self, caminho_pasta, dry_run=False, mover_para_lixeira=False, usar_data=False, quiet=False):
        """
        Organiza os arquivos da pasta especificada.
        dry_run: apenas mostra o que seria feito, não move nada
        mover_para_lixeira: move para lixeira ao invés de organizar
        usar_data: adiciona data no nome do arquivo
        quiet: modo silencioso (sem prints)
        """
        caminho = Path(caminho_pasta)
        self.quiet = quiet

        if not caminho.exists():
            if not self.quiet:
                print(f"❌ Erro: A pasta '{caminho_pasta}' não existe!")
            return

        if not self.quiet:
            print(f"\n📂 Organizando: {caminho.absolute()}")
            print("=" * 50)

        if dry_run:
            if not self.quiet:
                print("🔍 [MODO SIMULAÇÃO] - Nenhum arquivo será movido\n")

        arquivos = [f for f in caminho.iterdir() if f.is_file()]

        if not arquivos:
            if not self.quiet:
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

            # Nome do arquivo (com ou sem data)
            if usar_data and not dry_run:
                nome_arquivo = self._nome_com_data(arquivo)
            else:
                nome_arquivo = arquivo.name

            # Verificar duplicata
            hash_arquivo = self._calcular_hash_md5(arquivo)
            if hash_arquivo and self._verificar_duplicata(destino_path, nome_arquivo, hash_arquivo):
                if not self.quiet:
                    print(f"⏭️  {arquivo.name} → DUPLICATA (já existe em {destino_pasta}/)")
                continue

            novo_caminho = destino_path / nome_arquivo

            # Verificar se já existe arquivo com mesmo nome (mas conteúdo diferente)
            contador = 1
            while novo_caminho.exists():
                nome_base = Path(nome_arquivo).stem
                extensao_original = Path(nome_arquivo).suffix
                novo_nome = f"{nome_base}_{contador}{extensao_original}"
                novo_caminho = destino_path / novo_nome
                contador += 1

            if not self.quiet:
                print(f"📄 {arquivo.name} → {destino_pasta}/")

            if not dry_run:
                if mover_para_lixeira and SEND2TRASH_AVAILABLE:
                    # Move para lixeira (não organiza, só deleta de forma segura)
                    send2trash.send2trash(str(arquivo))
                else:
                    # Organiza normalmente
                    shutil.move(str(arquivo), str(novo_caminho))
                    self.arquivos_movidos.append({
                        "origem": str(arquivo),
                        "destino": str(novo_caminho),
                        "hash": hash_arquivo,
                        "data": datetime.now().isoformat()
                    })

        if not dry_run and not mover_para_lixeira:
            self._salvar_log()
            if not self.quiet:
                print(f"\n✅ Organização concluída! {len(arquivos)} arquivos processados.")
                print(f"📝 Log salvo em: {self.log_file}")

                # Mostrar estatísticas
                stats = self._contar_arquivos_por_pasta()
                if stats:
                    print("\n📊 Estatísticas por pasta:")
                    for pasta, count in sorted(stats.items()):
                        print(f"  📁 {pasta}: {count} arquivo(s)")

            # Notificação desktop (se disponível)
            if PLYER_AVAILABLE and not self.quiet:
                self._notificar(f"{len(self.arquivos_movidos)} arquivos organizados com sucesso!")

        elif dry_run:
            if not self.quiet:
                print(f"\n🔍 Simulação concluída! {len(arquivos)} arquivos seriam processados.")

        elif mover_para_lixeira:
            if not self.quiet:
                print(f"\n🗑️ {len(arquivos)} arquivos movidos para a lixeira.")

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

        # Manter apenas últimas 10 operações no log
        if len(historico) > 10:
            historico = historico[-10:]

        with open(self.log_file, 'w') as f:
            json.dump(historico, f, indent=2)

    def desfazer(self, num_operacao=-1):
        """Desfaz a última organização (ou uma específica)"""
        try:
            with open(self.log_file, 'r') as f:
                historico = json.load(f)
        except FileNotFoundError:
            if not self.quiet:
                print("❌ Nenhum log encontrado. Nada para desfazer.")
            return

        if not historico:
            if not self.quiet:
                print("❌ Histórico vazio.")
            return

        if num_operacao == -1:
            operacao = historico[-1]  # Última
        else:
            if num_operacao >= len(historico):
                if not self.quiet:
                    print(f"❌ Operação {num_operacao} não existe. Total: {len(historico)}")
                return
            operacao = historico[num_operacao]

        if not self.quiet:
            print(f"\n↩️ Desfazendo operação de {operacao['timestamp']}")
            print("=" * 50)

        for item in operacao['arquivos']:
            destino = Path(item['destino'])
            origem_original = Path(item['origem'])

            if destino.exists():
                shutil.move(str(destino), str(origem_original))
                if not self.quiet:
                    print(f"↩️ {destino.name} → {origem_original.parent}")
            else:
                if not self.quiet:
                    print(f"⚠️ Arquivo não encontrado: {destino.name}")

        if not self.quiet:
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
  %(prog)s --quiet            # Modo silencioso (sem prints)
  %(prog)s --lixeira          # Move arquivos para lixeira
  %(prog)s --com-data         # Adiciona data nos nomes dos arquivos
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
        help="Move para lixeira ao invés de organizar"
    )

    parser.add_argument(
        "--com-data",
        action="store_true",
        help="Adiciona data de modificação no nome dos arquivos"
    )

    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Modo silencioso (sem prints na tela)"
    )

    args = parser.parse_args()

    organizador = OrganizadorDownloads()

    if args.undo:
        organizador.desfazer()
    else:
        organizador.organizar(
            args.pasta,
            dry_run=args.dry_run,
            mover_para_lixeira=args.lixeira,
            usar_data=args.com_data,
            quiet=args.quiet
        )


if __name__ == "__main__":
    main()