"""
Monta o instalador do Certificados.

Rodar (de qualquer pasta), com o Python que tem as bibliotecas do programa:
    python instalador\\montar.py

1. PyInstaller monta o programa numa pasta (dist_programa\\Certificados), que
   abre mais rápido que o .exe único de antes;
2. o Inno Setup (instalador\\certificados.iss) empacota essa pasta em
   dist_instalador\\Instalar-Certificados-<versão>.exe;
3. uma cópia do instalador vai para a raiz do repositório (a anterior sai).

Depois, para publicar a versão no GitHub: commit + push (leva o instalador da
raiz) e a página Releases, que é onde o programa procura versão nova:
    gh release create v<versão> dist_instalador\\Instalar-Certificados-<versão>.exe
"""

import os
import shutil
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
PROJETO = os.path.dirname(AQUI)
sys.path.insert(0, PROJETO)

from certificados import VERSAO  # noqa: E402


def iscc():
    candidatos = [os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Inno Setup 6", "ISCC.exe"),
                  os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Inno Setup 6", "ISCC.exe"),
                  os.path.join(os.environ.get("ProgramFiles", ""), "Inno Setup 6", "ISCC.exe")]
    for c in candidatos:
        if os.path.isfile(c):
            return c
    sys.exit("Inno Setup 6 não encontrado (winget install JRSoftware.InnoSetup).")


def main():
    trabalho = os.path.join(PROJETO, "build_programa")
    saida = os.path.join(PROJETO, "dist_programa")
    shutil.rmtree(os.path.join(saida, "Certificados"), ignore_errors=True)
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--onedir", "--windowed",
                    "--name", "Certificados", "--icon", os.path.join(PROJETO, "icone.ico"),
                    "--add-data", f"{os.path.join(PROJETO, 'icone.ico')};.",
                    "--collect-all", "customtkinter", "--hidden-import", "comtypes.client",
                    "--paths", PROJETO, "--distpath", saida, "--workpath", trabalho, "--specpath", trabalho,
                    os.path.join(PROJETO, "programa.py")], check=True, cwd=PROJETO)
    subprocess.run([iscc(), f"/DVersao={VERSAO}", os.path.join(AQUI, "certificados.iss")], check=True)
    instalador = os.path.join(PROJETO, "dist_instalador", f"Instalar-Certificados-{VERSAO}.exe")
    copiar_para_a_raiz(instalador)
    print("\nInstalador:", instalador)


def copiar_para_a_raiz(instalador):
    """Uma cópia na raiz do repositório (só a versão atual): quem baixa o ZIP já leva o instalador."""
    raiz = os.path.dirname(PROJETO)
    for nome in os.listdir(raiz):
        if nome.startswith("Instalar-Certificados-") and nome.endswith(".exe"):
            os.remove(os.path.join(raiz, nome))
    shutil.copy2(instalador, raiz)


if __name__ == "__main__":
    main()
