"""
Aviso de versão nova: descobre qual é a última versão publicada no GitHub.

Não usa a API do GitHub (limite de 60 consultas por hora por endereço: numa
rede de empresa todo mundo sai pelo mesmo endereço). Abre o endereço
".../releases/latest", que o GitHub redireciona para ".../releases/tag/v0.3.6",
e lê a versão do endereço final.

NÃO chamar o PowerShell (nem outro programa) para isso: na 0.3.7 ele era a
2ª tentativa e o antivírus da empresa tratou o programa como suspeito e o
apagou (programa desconhecido abrindo PowerShell escondido para ir à internet).
"""

import re
import urllib.request

REPOSITORIO = "diogodimase-ctrl/Certificados-Python"
PAGINA_DOWNLOADS = f"https://github.com/{REPOSITORIO}/releases/latest"


class SemResposta(Exception):
    """Não deu para falar com o GitHub."""


def _numeros(versao):
    return tuple(int(n) for n in re.findall(r"\d+", versao or "")[:3])


def ultima_versao(tempo_limite=8):
    """"0.3.6" (a última publicada). Erro SemResposta se não conseguiu perguntar."""
    pedido = urllib.request.Request(PAGINA_DOWNLOADS, method="HEAD", headers={"User-Agent": "Certificados"})
    try:
        with urllib.request.urlopen(pedido, timeout=tempo_limite) as resposta:
            endereco = resposta.geturl()
    except Exception as e:
        raise SemResposta(str(e)) from e
    m = re.search(r"/releases/tag/v?([\d.]+)", endereco)
    if not m:
        raise SemResposta(f"endereço inesperado {endereco}")
    return m.group(1)


def link_do_instalador(versao):
    return f"https://github.com/{REPOSITORIO}/releases/download/v{versao}/Instalar-Certificados-{versao}.exe"


def versao_mais_nova(atual, tempo_limite=8):
    """(versão, link para baixar) se houver versão maior que "atual"; None se "atual"
    já é a mais nova. Erro SemResposta se não deu para saber."""
    nova = ultima_versao(tempo_limite)
    if _numeros(nova) <= _numeros(atual):
        return None
    return nova, link_do_instalador(nova)
