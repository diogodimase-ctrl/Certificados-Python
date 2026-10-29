"""
Tela "Corrigir um certificado" (era o Gerar_Manual_v1 do AHK), dentro da
janela do programa: o botão do cabeçalho troca entre ela e a rodada do mês.

À esquerda, a busca: em quais cursos do semestre aparece o docente (nome e,
se quiser, a data). "Preencher com os dados encontrados" copia a linha
escolhida para o formulário da direita, que dá para corrigir antes de gerar.
O PDF sai em C:\\Certificados\\Correções\\<MM.AA>; nada é enviado.
Cada PDF gerado conta no tempo economizado da tela Início.
"""

import os
import time
from datetime import date
from tkinter import filedialog

import customtkinter as ctk

import tema
from certificados import coordenadores, correcao, economia
from certificados.pdf import ConversorPowerPoint
from conferencia import em_segundo_plano
from tema import FONTE


LIMITE_TEMPO = 30 * 60      # tela esquecida aberta não vira "tempo do programa"


class TelaCorrecao(ctk.CTkFrame):

    def __init__(self, pai, app):
        super().__init__(pai, fg_color="transparent")
        self.app = app
        self.guardadas = {}           # planilhas já lidas nesta sessão
        self.achados = []
        self.ocupada = False
        self.inicio = None            # relógio desta correção (primeiro clique até o PDF)
        self.cadastro = coordenadores.Cadastro(app.locais.assinaturas, log=app.registrar)

        ctk.CTkLabel(self, text="Corrigir um certificado", font=(FONTE, 20, "bold"), text_color=tema.TITULO,
                     anchor="w").pack(fill="x", padx=32, pady=(16, 0))
        ctk.CTkLabel(self, text="Gera um certificado avulso. Só gera o PDF: nada é enviado e nada vai para o "
                                "SharePoint.",
                     text_color=tema.TEXTO_2, anchor="w").pack(fill="x", padx=32, pady=(2, 10))
        corpo = ctk.CTkFrame(self, fg_color="transparent")
        corpo.pack(fill="both", expand=True, padx=32, pady=(0, 16))
        corpo.grid_columnconfigure(0, weight=5, uniform="c")
        corpo.grid_columnconfigure(1, weight=4, uniform="c")
        corpo.grid_rowconfigure(0, weight=1)
        self._montar_busca(corpo)
        self._montar_formulario(corpo)

    def mostrar(self):
        """Chamado toda vez que a tela aparece: as abas da mestre podem ter chegado ou mudado."""
        self._desenhar_abas()
        if self.app.abas_mestre:
            if not self.ocupada:
                self.btn_procurar.configure(state="normal")
            if "abra a mestre" in self.status_busca.cget("text"):
                self.status_busca.configure(text="")
        else:
            self.status_busca.configure(text="Para procurar, abra a mestre na tela Início (aba do semestre). "
                                             "O formulário ao lado funciona mesmo assim.", text_color=tema.AVISO)
            self.btn_procurar.configure(state="disabled")
        self.after(50, self.ent_busca_nome.focus_set)

    def _comecou(self, *_):
        if self.inicio is None:
            self.inicio = time.monotonic()

    # -- busca --------------------------------------------------------------

    def _montar_busca(self, corpo):
        caixa = ctk.CTkFrame(corpo, fg_color=tema.CARTAO, corner_radius=10)
        caixa.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        ctk.CTkLabel(caixa, text="1. Procurar o docente nos cursos", font=(FONTE, 15, "bold"),
                     anchor="w").pack(fill="x", padx=16, pady=(14, 2))
        ctk.CTkLabel(caixa, text="Procura nas planilhas dos cursos das abas marcadas da mestre, em todos os meses. "
                                 "Marque as abas de anos passados para procurar nelas também.",
                     text_color=tema.APAGADO, anchor="w", justify="left", wraplength=620).pack(fill="x", padx=16)
        self.quadro_abas = ctk.CTkFrame(caixa, fg_color="transparent")
        self.quadro_abas.pack(fill="x", padx=16, pady=(8, 0))
        self.abas_vistas = []         # abas desenhadas por último (redesenha se a mestre mudar)
        self.vars_abas = {}           # aba -> BooleanVar (a escolha fica enquanto o programa estiver aberto)

        linha = ctk.CTkFrame(caixa, fg_color="transparent")
        linha.pack(fill="x", padx=16, pady=(10, 6))
        self.ent_busca_nome = ctk.CTkEntry(linha, placeholder_text="Nome do docente (ex.: Maria Souza)", height=36)
        self.ent_busca_nome.pack(side="left", fill="x", expand=True)
        self.ent_busca_data = ctk.CTkEntry(linha, placeholder_text="Data (opcional)", width=140, height=36)
        self.ent_busca_data.pack(side="left", padx=8)
        self.btn_procurar = ctk.CTkButton(linha, text="Procurar", width=120, height=36, command=self._procurar)
        self.btn_procurar.pack(side="left")
        for ent in (self.ent_busca_nome, self.ent_busca_data):
            ent.bind("<Return>", lambda e: self._procurar())
            ent.bind("<Key>", self._comecou, add="+")

        self.status_busca = ctk.CTkLabel(caixa, text="", text_color=tema.TEXTO_2, anchor="w", justify="left",
                                         wraplength=620)
        self.status_busca.pack(fill="x", padx=16)
        self.barra_busca = ctk.CTkProgressBar(caixa, height=6)
        self.barra_busca.set(0)

        detalhe_quadro = ctk.CTkFrame(caixa, fg_color="transparent")
        detalhe_quadro.pack(side="bottom", fill="x", padx=16, pady=(6, 14))
        ctk.CTkLabel(detalhe_quadro, text="Linha escolhida (dá para selecionar e copiar):", text_color=tema.APAGADO,
                     anchor="w").pack(fill="x")
        self.detalhe = ctk.CTkTextbox(detalhe_quadro, height=130, font=(FONTE, 13), wrap="word")
        self.detalhe.pack(fill="x")
        self.detalhe.configure(state="disabled")
        self.btn_preencher = ctk.CTkButton(detalhe_quadro, text="Preencher com os dados encontrados  →", height=40,
                                           font=(FONTE, 14, "bold"), state="disabled", command=self._preencher)
        self.btn_preencher.pack(fill="x", pady=(8, 0))

        quadro, self.arvore = tema.tabela(caixa, [("curso", "Curso", 210), ("semestre", "Semestre", 80),
                                                  ("mes", "Mês", 60), ("data", "Data", 95), ("aula", "Aula", 230)],
                                          alturas=8)
        quadro.pack(fill="both", expand=True, padx=16, pady=(6, 0))
        tema.pintar_tabelas(self)
        self.arvore.bind("<<TreeviewSelect>>", lambda e: self._mostrar_detalhe())
        self.arvore.bind("<Double-1>", lambda e: self._preencher())

    def _desenhar_abas(self):
        """Uma caixinha por aba de semestre da mestre. Na primeira vez, só a aba
        aberta na tela Início vem marcada."""
        abas = self.app._abas_de_semestre() if self.app.abas_mestre else []
        if abas == self.abas_vistas:
            if self.app.aba in self.vars_abas and not any(v.get() for v in self.vars_abas.values()):
                self.vars_abas[self.app.aba].set(True)
            return
        self.abas_vistas = abas
        for w in self.quadro_abas.winfo_children():
            w.destroy()
        if not abas:
            return
        marcadas = {a for a, v in self.vars_abas.items() if v.get()} or {self.app.aba}
        self.vars_abas = {a: ctk.BooleanVar(value=a in marcadas) for a in abas}
        ctk.CTkLabel(self.quadro_abas, text="Abas da mestre:", text_color=tema.TEXTO_2, anchor="w").grid(
            row=0, column=0, sticky="w", padx=(0, 8))
        por_linha = 6
        for i, aba in enumerate(abas):
            ctk.CTkCheckBox(self.quadro_abas, text=aba, variable=self.vars_abas[aba], width=90, checkbox_width=20,
                            checkbox_height=20).grid(row=i // por_linha, column=1 + i % por_linha, sticky="w", pady=2)
        botoes = ctk.CTkFrame(self.quadro_abas, fg_color="transparent")
        botoes.grid(row=0, column=2 + por_linha, sticky="e", padx=(8, 0))
        self.quadro_abas.grid_columnconfigure(1 + por_linha, weight=1)
        ctk.CTkButton(botoes, text="Todas", width=64, height=26, **tema.BOTAO_CONTORNO,
                      command=lambda: [v.set(True) for v in self.vars_abas.values()]).pack(side="left")
        ctk.CTkButton(botoes, text="Só a atual", width=84, height=26, **tema.BOTAO_CONTORNO,
                      command=lambda: [v.set(a == self.app.aba) for a, v in self.vars_abas.items()]).pack(
            side="left", padx=(6, 0))

    def _procurar(self):
        nome = self.ent_busca_nome.get().strip()
        data = self.ent_busca_data.get().strip()
        if self.ocupada or not self.app.abas_mestre:
            return
        if len(nome) < 3:
            self.status_busca.configure(text="Digite pelo menos parte do nome do docente.", text_color=tema.AVISO)
            return
        abas = [a for a in self.abas_vistas if self.vars_abas[a].get()]
        if not abas:
            self.status_busca.configure(text="Marque pelo menos uma aba da mestre.", text_color=tema.AVISO)
            return
        self.ocupada = True
        self.btn_procurar.configure(state="disabled")
        self.arvore.delete(*self.arvore.get_children())
        self._escrever_detalhe("")
        self.btn_preencher.configure(state="disabled")
        self._comecou()
        self.barra_busca.pack(fill="x", padx=16, pady=(4, 0), after=self.status_busca)
        app, mestre, guardadas = self.app, self.app.mestre, self.guardadas
        self.status_busca.configure(text=f"Lendo os cursos de {len(abas)} aba(s) da mestre…", text_color=tema.TEXTO_2)

        def progresso(i, total, curso):
            self.after(0, lambda: (self.barra_busca.set(i / max(total, 1)),
                                   self.status_busca.configure(text=f"Lendo {i + 1} de {total}: {curso}",
                                                               text_color=tema.TEXTO_2)))

        def trabalho():
            cursos, faltando = correcao.cursos_das_abas(mestre, abas, guardadas)
            return correcao.procurar(app.locais, cursos, nome, data, progresso, guardadas) + (faltando, len(abas))

        em_segundo_plano(self, trabalho, self._procurado, self._busca_falhou)

    def _procurado(self, resultado):
        self.ocupada = False
        self.btn_procurar.configure(state="normal")
        self.barra_busca.pack_forget()
        self.achados, sem_planilha, falhas, abas_faltando, n_abas = resultado
        for i, a in enumerate(self.achados):
            self.arvore.insert("", "end", iid=str(i), values=(a.curso, a.semestre, a.pasta_mes, a.data, a.aula))
        cursos = len({(a.curso, a.semestre) for a in self.achados})
        onde = "na aba marcada" if n_abas == 1 else f"nas {n_abas} abas marcadas"
        if self.achados:
            texto = (f"{len(self.achados)} aula(s) em {cursos} curso(s) {onde}. Escolha a linha e clique em "
                     "\"Preencher com os dados encontrados\" (ou dê dois cliques nela).")
            cor = tema.OK
        else:
            texto = (f"Não achei esse docente em nenhum curso {onde}. Confira a grafia, tire a data "
                     "ou marque mais abas.")
            cor = tema.AVISO
        extras = []
        if abas_faltando:
            extras.append(f"aba(s) não encontrada(s) na mestre: {', '.join(abas_faltando)}")
        if sem_planilha:
            extras.append(f"{len(sem_planilha)} curso(s) sem planilha encontrada")
        if falhas:
            extras.append(f"{len(falhas)} planilha(s) não abriram")
            for f in falhas:
                self.app.registrar(f"Correção — planilha não abriu: {f}")
        if extras:
            texto += "  (" + "; ".join(extras) + ")"
        self.status_busca.configure(text=texto, text_color=cor)
        if len(self.achados) == 1:
            self.arvore.selection_set("0")

    def _busca_falhou(self, erro, detalhe):
        self.ocupada = False
        self.btn_procurar.configure(state="normal")
        self.barra_busca.pack_forget()
        self.status_busca.configure(text=f"A busca falhou: {erro}", text_color=tema.ERRO)
        self.app.registrar(f"Correção — busca falhou: {erro}\n{detalhe}")

    def _mostrar_detalhe(self):
        sel = self.arvore.selection()
        if not sel:
            return
        a = self.achados[int(sel[0])]
        self.btn_preencher.configure(state="normal")
        self._escrever_detalhe(
            f"Docente: {a.docente}\n"
            f"Pós-graduação (como sai no certificado): {a.nome_pos}\n"
            f"Aula / disciplina: {a.aula}\n"
            f"Data: {a.data}    Horas: {a.horas}\n"
            f"Coordenação (mestre): {a.coordenacao}\n"
            f"Curso na mestre: {a.curso} ({a.codigo}), aba {a.semestre} · na planilha do curso: aba {a.aba}, "
            f"linha {a.linha}")

    def _escrever_detalhe(self, texto):
        self.detalhe.configure(state="normal")
        self.detalhe.delete("1.0", "end")
        self.detalhe.insert("1.0", texto)
        self.detalhe.configure(state="disabled")

    def _preencher(self):
        """Copia a linha escolhida para o formulário (substitui o que estava lá).
        O coordenador vem da coordenação da mestre, igual à rodada do mês."""
        sel = self.arvore.selection()
        if not sel or self.ocupada:
            return
        a = self.achados[int(sel[0])]
        self._comecou()
        for chave, valor in (("docente", a.docente), ("pos", a.nome_pos or a.curso), ("aula", a.aula),
                             ("data", a.data), ("horas", a.horas)):
            ent = self.campos[chave]
            ent.delete(0, "end")
            ent.insert(0, valor or "")
        coord = coordenadores.resolver(a.coordenacao, self.cadastro, log=lambda m: None)
        aviso = ""
        self.opt_titulo.set(correcao.TITULOS[0])       # não herdar o título da correção anterior
        self.opt_cargo.set(correcao.CARGOS[0])
        if coord.nome:
            self.cmb_coord.set(coord.nome)
            self._coordenador_escolhido(coord.nome)
            if coord.assinatura:
                self._definir_assinatura(coord.assinatura)
            if coord.pendente == "titulo":
                aviso = "Confira o título (Dr./Dra.) da coordenação: não está no cadastro."
        else:
            nomes = coord.nomes_da_planilha
            self.cmb_coord.set(nomes[0] if nomes else "")
            self.assinatura = ""
            self.lbl_assinatura.configure(text="(nenhuma)", text_color=tema.APAGADO)
            aviso = "Não achei a assinatura da coordenação: escolha o(a) coordenador(a) ou a assinatura."
        texto = "Dados copiados da planilha. Corrija o que estiver errado e clique em Gerar PDF."
        self.status_form.configure(text=texto + (f"\n! {aviso}" if aviso else ""),
                                   text_color=tema.AVISO if aviso else tema.TEXTO_2)

    # -- formulário ---------------------------------------------------------

    def _montar_formulario(self, corpo):
        caixa = ctk.CTkScrollableFrame(corpo, fg_color=tema.CARTAO, corner_radius=10)
        caixa.grid(row=0, column=1, sticky="nsew")
        caixa.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(caixa, text="2. Dados do certificado corrigido", font=(FONTE, 15, "bold"),
                     anchor="w").grid(row=0, column=0, columnspan=3, sticky="ew", padx=12, pady=(12, 8))
        self.campos = {}
        linha = 1

        def campo(chave, rotulo, valor="", dica=""):
            nonlocal linha
            ctk.CTkLabel(caixa, text=rotulo, anchor="w").grid(row=linha, column=0, sticky="w", padx=(12, 8), pady=4)
            ent = ctk.CTkEntry(caixa, height=34, placeholder_text=dica)
            if valor:
                ent.insert(0, valor)
            ent.bind("<Key>", self._comecou, add="+")
            ent.grid(row=linha, column=1, columnspan=2, sticky="ew", padx=(0, 12), pady=4)
            self.campos[chave] = ent
            linha += 1
            return ent

        campo("docente", "Docente")
        campo("pos", "Pós-graduação", dica="como deve sair no certificado")
        campo("aula", "Aula / disciplina")
        campo("data", "Data da aula", dica="dd/mm/aaaa")
        campo("horas", "Horas", dica="4  ·  2:30  ·  08:00 - 12:00  ·  4 horas")

        ctk.CTkLabel(caixa, text="Coordenador(a)", anchor="w").grid(row=linha, column=0, sticky="w", padx=(12, 8), pady=4)
        nomes = sorted((d["nome"] for d in self.cadastro.itens.values()), key=str.casefold)
        self.cmb_coord = ctk.CTkComboBox(caixa, values=nomes or [""], height=34, command=self._coordenador_escolhido)
        self.cmb_coord.set("")
        self.cmb_coord.grid(row=linha, column=1, columnspan=2, sticky="ew", padx=(0, 12), pady=4)
        self.cmb_coord._entry.bind("<FocusOut>", lambda e: self._coordenador_escolhido(self.cmb_coord.get(), False))
        linha += 1

        ctk.CTkLabel(caixa, text="Título e cargo", anchor="w").grid(row=linha, column=0, sticky="w", padx=(12, 8), pady=4)
        self.opt_titulo = ctk.CTkOptionMenu(caixa, values=correcao.TITULOS, width=130, command=self._titulo_escolhido)
        self.opt_titulo.grid(row=linha, column=1, sticky="w", pady=4)
        self.opt_cargo = ctk.CTkOptionMenu(caixa, values=correcao.CARGOS, width=210)
        self.opt_cargo.grid(row=linha, column=2, sticky="e", padx=(8, 12), pady=4)
        linha += 1

        ctk.CTkLabel(caixa, text="Assinatura", anchor="w").grid(row=linha, column=0, sticky="w", padx=(12, 8), pady=4)
        self.lbl_assinatura = ctk.CTkLabel(caixa, text="(nenhuma)", text_color=tema.APAGADO, anchor="w")
        self.lbl_assinatura.grid(row=linha, column=1, sticky="ew", pady=4)
        ctk.CTkButton(caixa, text="Escolher…", width=110, **tema.BOTAO_CONTORNO,
                      command=self._escolher_assinatura).grid(row=linha, column=2, sticky="e", padx=(8, 12), pady=4)
        self.assinatura = ""
        linha += 1

        campo("emissao", "Data de emissão", date.today().strftime("%d/%m/%Y"))

        self.chk_abrir = ctk.CTkCheckBox(caixa, text="Abrir o PDF quando ficar pronto")
        self.chk_abrir.select()
        self.chk_abrir.grid(row=linha, column=0, columnspan=3, sticky="w", padx=12, pady=(10, 4))
        linha += 1
        self.status_form = ctk.CTkLabel(caixa, text="", anchor="w", justify="left", wraplength=440)
        self.status_form.grid(row=linha, column=0, columnspan=3, sticky="ew", padx=12, pady=(4, 4))
        linha += 1
        botoes = ctk.CTkFrame(caixa, fg_color="transparent")
        botoes.grid(row=linha, column=0, columnspan=3, sticky="ew", padx=12, pady=(6, 12))
        self.btn_gerar = ctk.CTkButton(botoes, text="Gerar PDF", height=42, width=170, font=(FONTE, 15, "bold"),
                                       command=self._gerar)
        self.btn_gerar.pack(side="left")
        ctk.CTkButton(botoes, text="Limpar", width=100, height=42, **tema.BOTAO_CONTORNO,
                      command=self._limpar).pack(side="left", padx=8)
        ctk.CTkButton(botoes, text="Abrir pasta", width=120, height=42, **tema.BOTAO_CONTORNO,
                      command=self._abrir_pasta).pack(side="left")

    def _coordenador_escolhido(self, nome, sobrescrever=True):
        """Coordenador do cadastro: traz título e assinatura (dá para trocar)."""
        nome = (nome or "").strip()
        if not nome:
            return
        self._comecou()
        item = self.cadastro.obter(nome)
        if item and item["titulo"] and (sobrescrever or self.opt_titulo.get() == correcao.TITULOS[0]):
            self.opt_titulo.set(item["titulo"])
            self._titulo_escolhido(item["titulo"])
        if sobrescrever or not self.assinatura:
            caminho = self.cadastro.assinatura(nome) or coordenadores.encontrar_assinatura(
                self.cadastro.pasta, nome, log=lambda m: None)
            if caminho:
                self._definir_assinatura(caminho)

    def _titulo_escolhido(self, titulo):
        self.opt_cargo.set(correcao.CARGOS[1] if titulo.startswith(("Dra", "Profa")) else correcao.CARGOS[0])

    def _escolher_assinatura(self):
        caminho = filedialog.askopenfilename(parent=self.winfo_toplevel(),title="Assinatura do(a) coordenador(a)",
                                             initialdir=self.cadastro.pasta,
                                             filetypes=[("Imagens", "*.png *.jpg *.jpeg")])
        if caminho:
            self._definir_assinatura(os.path.normpath(caminho))

    def _definir_assinatura(self, caminho):
        self.assinatura = caminho
        self.lbl_assinatura.configure(text=os.path.basename(caminho), text_color=tema.TEXTO)

    def _pedido(self):
        v = {k: e.get().strip() for k, e in self.campos.items()}
        return correcao.Pedido(v["docente"], v["pos"], v["aula"], v["data"], v["horas"], self.cmb_coord.get().strip(),
                               self.opt_titulo.get(), self.opt_cargo.get(), self.assinatura, v["emissao"])

    def _gerar(self):
        if self.ocupada:
            return
        p = self._pedido()
        faltas = correcao.conferir(p)
        if faltas:
            self.status_form.configure(text="Falta:\n• " + "\n• ".join(faltas), text_color=tema.ERRO)
            return
        if not os.path.isfile(self.app.modelo or ""):
            self.status_form.configure(text=f"Modelo do certificado não encontrado: {self.app.modelo}",
                                       text_color=tema.ERRO)
            return
        self.ocupada = True
        self.btn_gerar.configure(state="disabled", text="Gerando…")
        self.status_form.configure(text="Gerando o PDF pelo PowerPoint…", text_color=tema.TEXTO_2)
        app, modelo, abrir = self.app, self.app.modelo, bool(self.chk_abrir.get())

        def trabalho():
            with ConversorPowerPoint(log=app.registrar) as conv:
                return correcao.gerar(p, app.locais, modelo, conv)

        em_segundo_plano(self, trabalho, lambda r: self._gerado(r, p, abrir), self._falhou)

    def _gerado(self, resultado, p, abrir):
        self.ocupada = False
        self.btn_gerar.configure(state="normal", text="Gerar PDF")
        pdf, avisos = resultado
        texto = f"✓ PDF pronto: {pdf}"
        if avisos:
            texto += "\n" + "\n".join(f"! {a}" for a in avisos)
        self.status_form.configure(text=texto, text_color=tema.OK)
        self.app.registrar(f"Correção gerada: {pdf} | {p.docente} | {p.pos} | {p.aula} | {p.data} | {p.horas}")
        if self.inicio is not None:       # gerar de novo sem mexer em nada não conta outra vez
            economia.registrar(1, min(time.monotonic() - self.inicio, LIMITE_TEMPO), tipo="correcao")
            self.inicio = None
        if abrir:
            self._abrir(pdf)

    def _falhou(self, erro, detalhe):
        self.ocupada = False
        self.btn_gerar.configure(state="normal", text="Gerar PDF")
        self.status_form.configure(text=f"Não gerou: {erro}", text_color=tema.ERRO)
        self.app.registrar(f"Correção falhou: {erro}\n{detalhe}")

    def _limpar(self):
        for chave, ent in self.campos.items():
            if chave != "emissao":
                ent.delete(0, "end")
        self.cmb_coord.set("")
        self.opt_titulo.set(correcao.TITULOS[0])
        self.opt_cargo.set(correcao.CARGOS[0])
        self.assinatura = ""
        self.lbl_assinatura.configure(text="(nenhuma)", text_color=tema.APAGADO)
        self.status_form.configure(text="")
        self.inicio = None

    def _abrir_pasta(self):
        os.makedirs(correcao.PASTA_CORRECOES, exist_ok=True)
        self._abrir(correcao.PASTA_CORRECOES)

    def _abrir(self, caminho):
        try:
            os.startfile(caminho)
        except OSError as e:
            self.status_form.configure(text=f"Não abriu {caminho}: {e}", text_color=tema.ERRO)
