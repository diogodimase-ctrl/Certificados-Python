"""
Escreve "Enviado" na planilha mestre, pelo Excel deste computador.

Só o Excel mexe no arquivo: a formatação, as outras abas e o que mais houver
na planilha ficam como estão (o openpyxl perderia coisas ao salvar). Só
escreve em célula VAZIA. Se a planilha estiver aberta só para leitura (outra
pessoa ou outro Excel com ela travada), não escreve nada e avisa.
"""

import os

TEXTO = "Enviado"
_SEM_PREENCHIMENTO = -4142        # xlNone


def _abertas(app):
    try:
        return [app.Workbooks.Item(i) for i in range(1, app.Workbooks.Count + 1)]
    except Exception:
        return []


def marcar_enviados(caminho, nome_aba, celulas, modelo=None, log=print):
    """celulas = [(linha, coluna)]; modelo = (linha, coluna) de uma célula que já
    tem "Enviado", para copiar a cor. Devolve quantas células foram escritas.
    Levanta RuntimeError com uma explicação se não der para escrever."""
    if not celulas:
        return 0
    import comtypes
    import comtypes.client
    comtypes.CoInitialize()
    app = wb = None
    criou_app = abriu = False
    try:
        alvo = os.path.normcase(os.path.abspath(caminho))
        try:      # já aberta no Excel da pessoa: escreve nela, mas quem salva é a pessoa (ou o salvamento automático)
            aberto = comtypes.client.GetActiveObject("Excel.Application")
            wb = next((w for w in _abertas(aberto) if os.path.normcase(str(w.FullName)) == alvo), None)
            app = aberto if wb is not None else None
        except Exception:
            pass
        if wb is None:      # senão, um Excel escondido só para isso
            app = comtypes.client.CreateObject("Excel.Application")
            criou_app = True
            app.Visible = False
            app.DisplayAlerts = False
            wb = app.Workbooks.Open(os.path.abspath(caminho), 0, False)
            abriu = True
        if wb.ReadOnly:
            raise RuntimeError("a planilha mestre está aberta só para leitura (alguém está com ela travada). "
                               "Tento de novo na próxima vez que o programa abrir.")
        ws = None
        for i in range(1, wb.Worksheets.Count + 1):
            if str(wb.Worksheets.Item(i).Name).strip().casefold() == nome_aba.strip().casefold():
                ws = wb.Worksheets.Item(i)
        if ws is None:
            raise RuntimeError(f"a aba {nome_aba} não existe mais na planilha mestre.")
        ref = ws.Cells.Item(*modelo) if modelo else None
        escritas = 0
        for linha, coluna in celulas:
            celula = ws.Cells.Item(linha, coluna)
            if str(celula.Value2 or "").strip():
                continue
            celula.Value2 = TEXTO
            if ref is not None:
                if ref.Interior.ColorIndex != _SEM_PREENCHIMENTO:
                    celula.Interior.Color = ref.Interior.Color
                celula.Font.Color = ref.Font.Color
            escritas += 1
        if escritas and abriu:
            wb.Save()
        log(f"Mestre: \"{TEXTO}\" escrito em {escritas} célula(s) da aba {nome_aba}"
            + ("." if abriu else " (a planilha estava aberta no Excel: ela é salva por lá)."))
        return escritas
    finally:
        try:
            if wb is not None and abriu:
                wb.Close(False)
            if app is not None and criou_app and app.Workbooks.Count == 0:
                app.Quit()
        except Exception:
            pass
        wb = app = None
        comtypes.CoUninitialize()
