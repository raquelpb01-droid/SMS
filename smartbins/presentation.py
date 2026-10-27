"""Gráficos de apresentação; não altera dados ou regras de estoque."""
import altair as alt
import pandas as pd
import streamlit as st


def render(chart):
    """Cores explícitas também nos eixos/legendas desenhados no canvas."""
    chart = (chart.configure(background='#FFFFFF')
             .configure_view(strokeOpacity=0)
             .configure_axis(labelColor='#495563', titleColor='#151515',
                             gridColor='#D8DFE6', labelFontSize=12, titleFontSize=13)
             .configure_legend(labelColor='#495563', titleColor='#151515',
                               labelFontSize=12, orient='bottom'))
    st.altair_chart(chart,theme=None,use_container_width=True)


def bars(data, color):
    frame = data.to_frame() if isinstance(data,pd.Series) else data.copy()
    columns = list(frame.columns)
    colors = [color]*len(columns) if isinstance(color,str) else color
    # Somente formato de exibição: nenhuma agregação ou cálculo de saldo aqui.
    frame.index = frame.index.map(str)
    values = frame.rename_axis('Referência').reset_index().melt(
        id_vars='Referência',var_name='Série',value_name='Valor')
    render(alt.Chart(values).mark_bar().encode(
        x=alt.X('Referência:N',axis=alt.Axis(labelAngle=-20,labelLimit=190),title=None),
        xOffset='Série:N',
        y=alt.Y('Valor:Q',title=None),
        color=alt.Color('Série:N',scale=alt.Scale(domain=columns,range=colors),title=None),
        tooltip=['Referência:N','Série:N','Valor:Q']))


def readings_chart(readings):
    values = pd.DataFrame({'Amostra':range(1,len(readings)+1),'Massa bruta (g)':readings})
    render(alt.Chart(values).mark_line(color='#3475AD',point=True).encode(
        x=alt.X('Amostra:O'),y=alt.Y('Massa bruta (g):Q',scale=alt.Scale(zero=False)),
        tooltip=['Amostra:O','Massa bruta (g):Q']))
