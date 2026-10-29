"""
Janela "Corrigir um certificado" (era o Gerar_Manual_v1 do AHK).

À esquerda, a busca: em quais cursos do semestre aparece o docente (nome e,
se quiser, a data). Ela só mostra; o formulário da direita é preenchido à mão.
O PDF sai em C:\\Certificados\\Correções\\<MM.AA>; nada é enviado.
"""

import os
from datetime import date
from tkinter import filedialog

import customtkinter as ctk

import tema
from certificados import coordenadores, correcao
from certificados.pdf import ConversorPowerPoint
from conferencia import em_segundo_plano
from tema import FONTE


class JanelaCorrecao(ctk.CTkToplevel):

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("Corrigir um certificado")
        self.geometry("1280x760")
        self.minsize(1100, 680)
        self.transient(app)
        self.guardadas = {}           # planilhas já lidas nesta janela
        self.achados = []
        self.ocupada = False
        self.cadastro = coordenadores.Cadastro(app.locais.assinaturas, log=app.registrar)

        ctk.CTkLabel(self, text="Corrigir um certificado", font=(FONTE, 20, "bold"), text_color=tema.TITULO,
                     anchor="w").pack(fill="x", padx=24, pady=(16, 0))
        ctk.CTkLabel(self, text="Gera um certificado avulso, com os dados digitados à mão. Só gera o PDF: "
                                "nada é enviado e nada vai para o SharePoint.",
                     text_color=tema.TEXTO_2, anchor="w").pack(fill="x", padx=24, pady=(2, 10))
        corpo = ctk.CTkFrame(self, fg_color="transparent")
        corpo.pack(fill="both", expand=True, padx=24, pady=(0, 16))
        corpo.grid_columnconfigure(0, weight=5, uniform="c")
        corpo.grid_columnconfigure(1, weight=4, uniform="c")
        corpo.grid_rowconfigure(0, weight=1)
        self._montar_busca(corpo)
        self._montar_formulario(corpo)
        self.after(150, self._mostrar)

    def _mostrar(self):
        self.lift()
        self.focus_force()
        self.ent_busca_nome.focus_set()

    # -- busca --------------------------------------------------------------

    def _montar_busca(self, corpo):
        caixa = ctk.CTkFrame(corpo, fg_color=tema.CARTAO, corner_radius=10)
        caixa.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        ctk.CTkLabel(caixa, text="1. Procurar o docente nos cursos", font=(FONTE, 15, "bold"),
                     anchor="w").pack(fill="x", padx=16, pady=(14, 2))
        aba = self.app.aba or "—"
        ctk.CTkLabel(caixa, text=f"Procura nas planilhas dos cursos da aba {aba} da mestre, em todos os meses. "
                                 "Só mostra: copie o que precisar para o formulário.",
                     text_color=tema.APAGADO, anchor="w", justify="left", wraplength=620).pack(fill="x", padx=16)

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

        self.status_busca = ctk.CTkLabel(caixa, text="", text_color=tema.TEXTO_2, anchor="w", justify="left")
        self.status_busca.pack(fill="x", padx=16)
        self.barra_busca = ctk.CTkProgressBar(caixa, height=6)
        self.barra_busca.set(0)

        detalhe_quadro = ctk.CTkFrame(caixa, fg_color="transparent")
        detalhe_quadro.pack(side="bottom", fill="x", padx=16, pady=(6, 14))
        ctk.CTkLabel(detalhe_quadro, text="Linha escolhida (dá para selecionar e copiar):", text_color=tema.APAGADO,
                     anchor="w").pack(fill="x")
        self.detalhe = ctk.CTkTextbox(detalhe_quadro, height=150, font=(FONTE, 13), wrap="word")
        self.detalhe.pack(fill="x")
        self.detalhe.configure(state="disabled")

        quadro, self.arvore = tema.tabela(caixa, [("curso", "Curso", 230), ("mes", "Mês", 60),
                                                  ("data", "Data", 95), ("aula", "Aula", 260)], alturas=8)
        quadro.pack(fill="both", expand=True, padx=16, pady=(6, 0))
        tema.pintar_tabelas(self)
        self.arvore.bind("<<TreeviewSelect>>", lambda e: self._mostrar_detalhe())
        if not self.app.cursos:
            self.status_busca.configure(text="Para procurar, abra a mestre na tela Início (aba do semestre). "
                                             "O formulário ao lado funciona mesmo assim.", text_color=tema.AVISO)
            self.btn_procurar.configure(state="disabled")

    def _procurar(self):
        nome = self.ent_busca_nome.get().strip()
        data = self.ent_busca_data.get().strip()
        if self.ocupada or not self.app.cursos:
            return
        if len(nome) < 3:
            self.status_busca.configure(text="Digite pelo menos parte do nome do docente.", text_color=tema.AVISO)
            return
        self.ocupada = True
        self.btn_procurar.configure(state="disabled")
        self.arvore.delete(*self.arvore.get_children())
        self._escrever_detalhe("")
        self.barra_busca.pack(fill="x", padx=16, pady=(4, 0), after=self.status_busca)
        app, cursos, aba, guardadas = self.app, list(self.app.cursos), self.app.aba, self.guardadas

        def progresso(i, total, curso):
            self.after(0, lambda: (self.barra_busca.set(i / max(total, 1)),
                                   self.status_busca.configure(text=f"Lendo {i + 1} de {total}: {curso}",
                                                               text_color=tema.TEXTO_2)))

        em_segundo_plano(self, lambda: correcao.procurar(app.locais, cursos, aba, nome, data, progresso, guardadas),
                         self._procurado, self._busca_falhou)

    def _procurado(self, resultado):
        self.ocupada = False
        self.btn_procurar.configure(state="normal")
        self.barra_busca.pack_forget()
        self.achados, sem_planilha, falhas = resultado
        for i, a in enumerate(self.achados):
            self.arvore.insert("", "end", iid=str(i), values=(a.curso, a.pasta_mes, a.data, a.aula))
        cursos = len({a.curso for a in self.achados})
        if self.achados:
            texto = f"{len(self.achados)} aula(s) em {cursos} curso(s). Clique numa linha para ver tudo."
            cor = tema.OK
        else:
            texto, cor = "Não achei esse docente em nenhum curso do semestre. Confira a grafia ou tire a data.", tema.AVISO
        extras = []
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
        self._escrever_detalhe(
            f"Docente: {a.docente}\n"
            f"Pós-graduação (como sai no certificado): {a.nome_pos}\n"
            f"Aula / disciplina: {a.aula}\n"
            f"Data: {a.data}    Horas: {a.horas}\n"
            f"Coordenação (mestre): {a.coordenacao}\n"
            f"Curso na mestre: {a.curso} ({a.codigo}) · aba {a.aba}, linha {a.linha}")

    def _escrever_detalhe(self, texto):
        self.detalhe.configure(state="normal")
        self.detalhe.delete("1.0", "end")
        self.detalhe.insert("1.0", texto)
        self.detalhe.configure(state="disabled")

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
        caminho = filedialog.askopenfilename(parent=self, title="Assinatura do(a) coordenador(a)",
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

    def _abrir_pasta(self):
        os.makedirs(correcao.PASTA_CORRECOES, exist_ok=True)
        self._abrir(correcao.PASTA_CORRECOES)

    def _abrir(self, caminho):
        try:
            os.startfile(caminho)
        except OSError as e:
            self.status_form.configure(text=f"Não abriu {caminho}: {e}", text_color=tema.ERRO)
