"""
Aviso de versão nova: descobre qual é a última versão publicada no GitHub.

Não usa a API do GitHub (limite de 60 consultas por hora por endereço: numa
rede de empresa todo mundo sai pelo mesmo endereço). Abre o endereço
".../releases/latest", que o GitHub redireciona para ".../releases/tag/v0.3.6",
e lê a versão do endereço final.

Duas tentativas: 1ª pelo Python; 2ª pelo PowerShell, que usa o proxy e o login
do Windows do mesmo jeito que o navegador (o Python não entende o proxy
automático das redes de empresa).
"""

import re
import subprocess
import urllib.request

REPOSITORIO = "diogodimase-ctrl/Certificados-Python"
PAGINA_DOWNLOADS = f"https://github.com/{REPOSITORIO}/releases/latest"


class SemResposta(Exception):
    """Nenhuma das tentativas conseguiu falar com o GitHub."""


def _numeros(versao):
    return tuple(int(n) for n in re.findall(r"\d+", versao or "")[:3])


def _pelo_python(tempo_limite):
    pedido = urllib.request.Request(PAGINA_DOWNLOADS, method="HEAD", headers={"User-Agent": "Certificados"})
    with urllib.request.urlopen(pedido, timeout=tempo_limite) as resposta:
        return resposta.geturl()


def _pelo_powershell(tempo_limite):
    comando = (
        "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; "
        "$p = [Net.WebRequest]::DefaultWebProxy; $p.Credentials = [Net.CredentialCache]::DefaultCredentials; "
        f"$r = Invoke-WebRequest -UseBasicParsing -Method Head -TimeoutSec {tempo_limite} '{PAGINA_DOWNLOADS}'; "
        "$r.BaseResponse.ResponseUri.AbsoluteUri"
    )
    saida = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", comando],
                           capture_output=True, encoding="oem", errors="replace", timeout=tempo_limite + 10,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if saida.returncode != 0 or not saida.stdout.strip():
        raise OSError((saida.stderr or "sem resposta").strip().splitlines()[0][:200])
    return saida.stdout.strip()


def ultima_versao(tempo_limite=8):
    """"0.3.6" (a última publicada). Erro SemResposta se não conseguiu perguntar."""
    erros = []
    for nome, tentativa in (("Python", _pelo_python), ("PowerShell", _pelo_powershell)):
        try:
            endereco = tentativa(tempo_limite)
        except Exception as e:
            erros.append(f"{nome}: {e}")
            continue
        m = re.search(r"/releases/tag/v?([\d.]+)", endereco)
        if m:
            return m.group(1)
        erros.append(f"{nome}: endereço inesperado {endereco}")
    raise SemResposta(" | ".join(erros))


def link_do_instalador(versao):
    return f"https://github.com/{REPOSITORIO}/releases/download/v{versao}/Instalar-Certificados-{versao}.exe"


def versao_mais_nova(atual, tempo_limite=8):
    """(versão, link para baixar) se houver versão maior que "atual"; None se "atual"
    já é a mais nova. Erro SemResposta se não deu para saber."""
    nova = ultima_versao(tempo_limite)
    if _numeros(nova) <= _numeros(atual):
        return None
    return nova, link_do_instalador(nova)
