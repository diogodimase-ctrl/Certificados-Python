"""
Onde ficam as coisas: OneDrive da empresa, pasta "Declarações", planilhas de
curso, modelo, assinaturas e pastas de saída. Mesmas regras de
ObterOneDriveEinstein / ObterCaminhosCompartilhados / LocalizarPlanilhaCursoDinamica.
"""

import glob
import os
import re
from dataclasses import dataclass

from . import textos

NOME_DECLARACOES = "Planilha compartilhada - Declarações"
NOME_MESTRE = "Controle de Declaração de Aula.xlsx"
NOME_MODELO = "Certificado_Modelo_AHK.pptx"
NOME_ASSINATURAS = "Coordenadores e suas assinaturas"
NOME_LOGO = "_logo_einstein.jpg"
PASTA_ASSINATURAS_LOCAL = r"C:\CAssinaturas"


def onedrive_empresa():
    """ObterOneDriveEinstein."""
    perfil = os.environ.get("USERPROFILE", "")
    candidatos = [
        os.path.join(perfil, "OneDrive - Hospital Albert Einstein"),
        os.environ.get("OneDriveCommercial", ""),
        os.environ.get("OneDrive", ""),
        os.path.join(perfil, "OneDrive - Sociedade Beneficente Israelita Brasileira Hospital Albert Einstein"),
    ]
    for c in candidatos:
        if c and os.path.isdir(c):
            return c
    pastas = sorted(p for p in glob.glob(os.path.join(perfil, "OneDrive*")) if os.path.isdir(p))
    for p in pastas:
        nome = os.path.basename(p)
        if "Einstein" in nome or "Hospital" in nome:
            return p
    return pastas[0] if pastas else ""


@dataclass
class Locais:
    """ObterCaminhosCompartilhados."""
    raiz_onedrive: str
    declaracoes: str
    planilha_mestre: str
    modelo: str
    assinaturas: str
    logo: str

    @classmethod
    def descobrir(cls, raiz=None):
        raiz = onedrive_empresa() if raiz is None else raiz
        decl = os.path.join(raiz, NOME_DECLARACOES) if raiz else ""
        assin_nuvem = os.path.join(decl, NOME_ASSINATURAS) if decl else ""
        assinaturas = assin_nuvem if assin_nuvem and os.path.isdir(assin_nuvem) else PASTA_ASSINATURAS_LOCAL
        # O AHK usa o logo de C:\CAssinaturas. Se não estiver lá, procura na
        # pasta de assinaturas da nuvem (o que permite rodar em outro computador).
        logo = os.path.join(PASTA_ASSINATURAS_LOCAL, NOME_LOGO)
        if not os.path.isfile(logo) and assin_nuvem:
            logo = os.path.join(assin_nuvem, NOME_LOGO)
        return cls(
            raiz_onedrive=raiz,
            declaracoes=decl,
            planilha_mestre=os.path.join(decl, NOME_MESTRE) if decl else "",
            modelo=os.path.join(decl, NOME_MODELO) if decl else "",
            assinaturas=assinaturas,
            logo=logo,
        )


_PALAVRAS_IGNORADAS = {"para", "com", "pos", "graduacao", "especializacao", "em", "de", "da", "do", "dos", "das"}


def localizar_planilha_do_curso(raiz, nome_curso, unidade="", semestre="", cache=None):
    """LocalizarPlanilhaCursoDinamica: procura o .xlsx do curso nas pastas
    "Planilha compartilhada - Pós-graduação*" (e em Declarações), do critério
    mais forte (curso + unidade + semestre) para o mais fraco (só o curso).
    "cache" (dict) guarda a lista de arquivos de cada pasta entre chamadas
    (a busca da correção chama isto para muitos cursos de uma vez)."""
    if not raiz or not os.path.isdir(raiz):
        return ""
    palavras = [w for w in textos.normalizar(nome_curso).split(" ")
                if len(w) >= 3 and w not in _PALAVRAS_IGNORADAS]
    var_unidade = textos.variacoes_unidade(unidade)
    var_semestre = textos.variacoes_semestre(semestre)

    pastas = []
    for s in var_semestre:
        p = os.path.join(raiz, f"Planilha compartilhada - Pós-graduação {s}")
        if os.path.isdir(p) and p not in pastas:
            pastas.append(p)
    for p in sorted(glob.glob(os.path.join(raiz, "Planilha compartilhada - Pós-graduação*"))):
        if os.path.isdir(p) and p not in pastas:
            pastas.append(p)
    decl = os.path.join(raiz, NOME_DECLARACOES)
    if os.path.isdir(decl):
        pastas.append(decl)

    normalizados = []
    for pasta in pastas:
        if cache is None or pasta not in cache:
            lista = []
            for atual, _, nomes in os.walk(pasta):
                lista += [os.path.join(atual, n) for n in sorted(nomes) if n.lower().endswith(".xlsx")]
            lista = [(a, textos.normalizar(a)) for a in lista]
            if cache is None:
                normalizados += lista
                continue
            cache[pasta] = lista
        normalizados += cache[pasta]

    def tem_curso(n):
        return all(k in n for k in palavras)

    def tem_unidade(n):
        return any(u in n for u in var_unidade)

    def tem_semestre(n):
        return any(s in n for s in var_semestre)

    criterios = []
    if palavras and var_unidade and var_semestre:
        criterios.append(lambda n: tem_curso(n) and tem_unidade(n) and tem_semestre(n))
    if palavras and var_unidade:
        criterios.append(lambda n: tem_curso(n) and tem_unidade(n))
    if palavras and var_semestre:
        criterios.append(lambda n: tem_curso(n) and tem_semestre(n))
    if palavras:
        criterios.append(tem_curso)
    for criterio in criterios:
        for arq, n in normalizados:
            if criterio(n):
                return arq
    return ""


def pasta_da_pos(pasta_sigla, posgrad, codigo):
    """Nome da pasta da pós dentro de Declarações\\<semestre>\\<sigla>, sem criar
    pastas paralelas: 1º usa a que já existe como "<Pós> (<código>)"; 2º a que
    já existe só como "<Pós>"; senão, o nome novo é "<Pós> (<código>)".
    A comparação ignora maiúsculas e acentos (devolve o nome como está na pasta)."""
    pos = textos.sanitizar_nome_arquivo(posgrad)
    codigo = textos.sanitizar_nome_arquivo(codigo) if str(codigo or "").strip() else ""
    com_codigo = f"{pos} ({codigo})" if codigo else pos
    try:
        existentes = [n for n in os.listdir(pasta_sigla) if os.path.isdir(os.path.join(pasta_sigla, n))]
    except OSError:
        existentes = []
    for procurado in (com_codigo, pos):
        alvo = textos.normalizar(procurado)
        for nome in existentes:
            if textos.normalizar(nome) == alvo:
                return nome
    return com_codigo


def separar_codigo(nome_pasta):
    """"Medicina da Dor (2026-A-CEP-1S)" -> ("Medicina da Dor", "2026-A-CEP-1S");
    sem código da turma no fim -> (nome, "")."""
    m = re.match(r"^(.*?)\s*\((\d{4}-[^()]+)\)\s*$", nome_pasta or "")
    return (m.group(1).strip(), m.group(2).strip()) if m else ((nome_pasta or "").strip(), "")


def caminho_unico(pasta, nome_base, extensao):
    """CaminhoUnico: "Nome.pdf", depois "Nome.1.pdf", "Nome.2.pdf"..."""
    caminho = os.path.join(pasta, nome_base + extensao)
    contador = 1
    while os.path.exists(caminho):
        caminho = os.path.join(pasta, f"{nome_base}.{contador}{extensao}")
        contador += 1
    return caminho
