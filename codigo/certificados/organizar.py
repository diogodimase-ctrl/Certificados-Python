r"""
Leva o que está em Declarações\Enviados para o lugar oficial:
Declarações\<AAAA-5 ou AAAA-6>\<Unidade>\<Pós>\<MM.AA>.

A pasta "Enviados" é da fase 5 do fluxo: ele guardava lá o lote depois do
envio, em Enviados\<Pós (código da turma)>\<MM.AA>. O código da turma, entre
parênteses no nome da pasta, dá a unidade (CEP, PTA...) e o semestre da turma.

Primeiro planejar() mostra o que vai para onde; só mover() mexe nos arquivos.
"""

import os
import re
import shutil
import time
from dataclasses import dataclass

from . import caminhos, textos

PASTA_ENVIADOS = "Enviados"


@dataclass
class Movimento:
    origem: str           # Enviados\<curso>\<mês>
    destino: str          # "" se não deu para saber
    pdfs: int
    problema: str = ""

    @property
    def rotulo_origem(self):
        return os.path.join(*self.origem.replace("\\", "/").split("/")[-3:])


def _listar(pasta):
    try:
        return sorted(os.listdir(pasta))
    except OSError:
        return []


def _destino(declaracoes, nome_pasta_curso, mes):
    """("Cardiologia Clínica (2026-A-PTA-1S)", "04.26") -> caminho oficial, ou ("", problema)."""
    m = re.match(r"^(.*?)\s*\(([^()]+)\)\s*(?:\(\d+\)\s*)?$", nome_pasta_curso)
    if not m:
        return "", "sem o código da turma no nome da pasta"
    pos, codigo = m.group(1).strip(), m.group(2).strip()
    sigla = textos.sigla_unidade(codigo)
    semestre = textos.semestre_da_turma("", codigo)
    if not semestre or not sigla or sigla == codigo:
        return "", f"não entendi o código da turma '{codigo}'"
    pasta_sigla = os.path.join(declaracoes, semestre, textos.sanitizar_nome_arquivo(sigla))
    return os.path.join(pasta_sigla, caminhos.pasta_da_pos(pasta_sigla, pos, codigo), mes), ""


def planejar(declaracoes):
    enviados = os.path.join(declaracoes, PASTA_ENVIADOS)
    plano = []
    for curso in _listar(enviados):
        pasta_curso = os.path.join(enviados, curso)
        if not os.path.isdir(pasta_curso):
            continue
        for mes in _listar(pasta_curso):
            origem = os.path.join(pasta_curso, mes)
            if not os.path.isdir(origem):
                continue
            pdfs = sum(1 for n in _listar(origem) if n.lower().endswith(".pdf"))
            if not pdfs:
                continue
            if not re.fullmatch(r"\d{2}\.\d{2}", mes):
                plano.append(Movimento(origem, "", pdfs, f"'{mes}' não é uma pasta de mês (MM.AA)"))
                continue
            destino, problema = _destino(declaracoes, curso, mes)
            plano.append(Movimento(origem, destino, pdfs, problema))
    return plano


def limpar_para_enviar(declaracoes, log=print, minutos=30, agora=None):
    """Apaga as pastas de curso VAZIAS da Para Enviar. O fluxo, depois de mover
    os PDFs, apaga só a pasta do mês e a do curso fica para trás. Só sai a que
    está vazia (nem subpasta) e parada há "minutos" (uma pasta recém-criada pode
    estar no meio da sincronização). A exclusão vai para a Lixeira do site.
    Devolve os nomes apagados."""
    para_enviar = os.path.join(declaracoes, "Para Enviar")
    agora = agora or time.time()
    apagadas = []
    for nome in _listar(para_enviar):
        pasta = os.path.join(para_enviar, nome)
        try:
            if not os.path.isdir(pasta) or _listar(pasta) or agora - os.path.getmtime(pasta) < minutos * 60:
                continue
            os.rmdir(pasta)
            apagadas.append(nome)
            log(f"Para Enviar: pasta vazia apagada — {nome}")
        except OSError as e:
            log(f"Para Enviar: não consegui apagar a pasta vazia {nome}: {e}")
    return apagadas


def mover(plano, log=print):
    """Move os PDFs de cada item sem problema. Se o mesmo PDF já existe no
    destino (mesmo tamanho), o de Enviados é só apagado; se existe diferente,
    o de Enviados entra com " (Enviados)" no nome. Pastas que ficam vazias saem.
    Devolve (pdfs movidos, erros)."""
    movidos, erros = 0, []
    for mov in plano:
        if mov.problema or not mov.destino:
            continue
        try:
            os.makedirs(mov.destino, exist_ok=True)
            for nome in _listar(mov.origem):
                if not nome.lower().endswith(".pdf"):
                    continue
                de, para = os.path.join(mov.origem, nome), os.path.join(mov.destino, nome)
                if os.path.exists(para):
                    if os.path.getsize(para) == os.path.getsize(de):
                        os.remove(de)
                        continue
                    base, ext = os.path.splitext(nome)
                    para = os.path.join(mov.destino, f"{base} (Enviados){ext}")
                shutil.move(de, para)
                movidos += 1
            for pasta in (mov.origem, os.path.dirname(mov.origem)):
                if not _listar(pasta):
                    os.rmdir(pasta)
            log(f"Enviados → {mov.destino}")
        except OSError as e:
            erros.append(f"{mov.rotulo_origem}: {e}")
            log(f"Não consegui mover {mov.origem}: {e}")
    return movidos, erros
