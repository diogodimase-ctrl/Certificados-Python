"""
Correção avulsa (era o Gerar_Manual_v1 do AHK): um certificado por vez, com
todos os campos digitados à mão. Só gera o PDF, não manda e-mail.

Ajuda no preenchimento: procurar() acha em quais cursos do semestre (planilha
de cada curso, todas as abas de mês) aparece um docente, com a data opcional.
"""

import os
import re
import shutil
import tempfile
from dataclasses import dataclass

from . import caminhos, horas, modelo, planilhas, textos

PASTA_CORRECOES = r"C:\Certificados\Correções"
TITULOS = ["(Nenhum)", "Dr.", "Dra.", "Prof. Dr.", "Profa. Dra.", "Prof.", "Profa."]
CARGOS = ["Coordenador do Curso", "Coordenadora do Curso", "Coordenador(a) do Curso"]


# ---------------------------------------------------------------------------
# Busca do docente
# ---------------------------------------------------------------------------

@dataclass
class Achado:
    curso: str            # nome da pós na mestre
    codigo: str           # código da turma
    coordenacao: str      # coluna A da mestre
    nome_pos: str         # A2 da planilha do curso (o que sai no certificado)
    aba: str
    pasta_mes: str
    linha: int
    docente: str
    aula: str
    data: str
    horas: str


def nome_confere(procurado, nome):
    """Todas as palavras digitadas estão no nome (sem acento, título e de/da/do):
    "maria souza" acha "Dra. Maria Aparecida de Souza"."""
    buscadas = textos.palavras_do_nome(textos.chave_nome(procurado))
    palavras = textos.palavras_do_nome(textos.chave_nome(nome))
    return bool(buscadas) and all(p in palavras for p in buscadas)


def data_confere(procurada, data):
    """"6/4", "06/04/26" ou "06.04.2026" contra a data da planilha ("06/04/2026").
    Sem ano digitado, vale qualquer ano. Data vazia vale tudo."""
    txt = str(procurada or "").strip()
    if not txt:
        return True
    m = re.fullmatch(r"(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2,4}))?", txt)
    d = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", str(data or "").strip())
    if not m or not d:
        return False
    if (int(m.group(1)), int(m.group(2))) != (int(d.group(1)), int(d.group(2))):
        return False
    return not m.group(3) or m.group(3)[-2:] == d.group(3)[-2:]


def procurar(locais, cursos, aba_mestre, nome, data="", progresso=None, guardadas=None):
    """Devolve (achados, cursos sem planilha, falhas). "guardadas" é um dict
    para não reabrir a mesma planilha a cada busca (chave = caminho + data
    de modificação)."""
    guardadas = {} if guardadas is None else guardadas
    achados, sem_planilha, falhas = [], [], []
    for i, c in enumerate(cursos):
        if progresso:
            progresso(i, len(cursos), c.posgrad)
        caminho = caminhos.localizar_planilha_do_curso(locais.raiz_onedrive, c.posgrad, c.unidade, aba_mestre)
        if not caminho:
            sem_planilha.append(c.posgrad)
            continue
        try:
            chave = f"{os.path.normcase(caminho)}|{os.path.getmtime(caminho):.0f}"
            if chave not in guardadas:
                guardadas[chave] = planilhas.linhas_de_todos_os_meses(caminho)
        except Exception as e:
            falhas.append(f"{c.posgrad}: {e}")
            continue
        for aba, pasta_mes, nome_pos, r in guardadas[chave]:
            if nome_confere(nome, r.nome) and data_confere(data, r.data_aula):
                achados.append(Achado(c.posgrad, c.unidade, c.coordenacao, nome_pos, aba, pasta_mes, r.linha,
                                      r.nome, r.curso, r.data_aula, r.horas_formatadas))
    achados.sort(key=lambda a: (a.curso.casefold(), a.pasta_mes[3:], a.pasta_mes[:2], a.data))
    return achados, sem_planilha, falhas


# ---------------------------------------------------------------------------
# Geração
# ---------------------------------------------------------------------------

@dataclass
class Pedido:
    docente: str
    pos: str
    aula: str
    data: str
    horas: str
    coordenador: str
    titulo: str
    cargo: str
    assinatura: str
    data_emissao: str

    def assina_como(self):
        titulo = "" if self.titulo in ("", TITULOS[0]) else self.titulo
        return f"{titulo} {textos.sem_titulo(self.coordenador)}".strip()


def horas_do_certificado(digitado):
    """"4" -> "4 horas"; "08:00 - 12:00" -> "4 horas"; "4 horas" fica. Texto
    que não dá para entender sai como foi digitado (igual ao AHK)."""
    txt = str(digitado or "").strip()
    if not txt:
        return ""
    curto = horas.formatar_duracao_digitada(txt)
    if curto:
        return curto
    formatado = horas.formatar_horas(txt)
    return txt if "invalido" in formatado.lower() else formatado


def conferir(p):
    """Lista do que falta ou está errado ([] = pode gerar)."""
    faltas = []
    for valor, rotulo in ((p.docente, "Nome do docente"), (p.pos, "Pós-graduação"), (p.aula, "Aula / disciplina"),
                          (p.horas, "Horas"), (p.coordenador, "Coordenador(a)")):
        if not str(valor or "").strip():
            faltas.append(f"{rotulo} em branco")
    if not horas.corrigir_data_digitada(p.data):
        faltas.append("Data da aula inválida (use dd/mm/aaaa)")
    if not horas.corrigir_data_digitada(p.data_emissao):
        faltas.append("Data de emissão inválida (use dd/mm/aaaa)")
    if not p.assinatura or not os.path.isfile(p.assinatura):
        faltas.append("Assinatura não escolhida")
    return faltas


def caminho_do_pdf(p, pasta=None):
    """C:\\Certificados\\Correções\\<MM.AA>\\<Docente> (<dd.mm.aaaa>).pdf: o mesmo nome
    do certificado original, para responder o e-mail com o arquivo certo."""
    pasta = pasta or PASTA_CORRECOES
    data = horas.corrigir_data_digitada(p.data)
    dia, mes, ano = data.split("/")
    nome = f"{textos.sanitizar_nome_arquivo(p.docente.strip())} ({dia}.{mes}.{ano})"
    return os.path.join(pasta, f"{mes}.{ano[2:]}", nome + ".pdf")


def gerar(p, locais, modelo_pptx, conversor, pasta=None):
    """Gera o PDF (substitui uma correção anterior com o mesmo nome).
    Devolve (caminho do PDF, avisos)."""
    destino = caminho_do_pdf(p, pasta)
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    if os.path.exists(destino):
        try:
            os.remove(destino)
        except OSError as e:
            raise RuntimeError(f"Feche o PDF anterior antes de gerar de novo:\n{destino}") from e
    avisos = []
    base = modelo.criar_modelo_base(modelo_pptx, p.assina_como(), p.cargo, horas.corrigir_data_digitada(p.data_emissao),
                                    p.assinatura, locais.logo, avisos)
    temp = tempfile.mkdtemp(prefix="certificado_correcao_")
    try:
        pptx = os.path.join(temp, "correcao.pptx")
        modelo.preencher_certificado(base, p.docente.strip(), p.pos.strip(), p.aula.strip(),
                                     horas.corrigir_data_digitada(p.data), horas_do_certificado(p.horas), pptx)
        conversor.converter(pptx, destino)
    finally:
        shutil.rmtree(temp, ignore_errors=True)
    return destino, avisos
