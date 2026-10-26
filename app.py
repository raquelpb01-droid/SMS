"""Interface acadêmica Smart Bins — nenhum acesso externo ao SAP ou câmeras."""
import io
import json
from pathlib import Path
import pandas as pd
import streamlit as st
from smartbins.core import System, EMPLOYEES, UNCONFIRMED

st.set_page_config(page_title='Smart Bins | Gestão de estoques',page_icon='📦',layout='wide')
st.markdown('''<style>.stApp{background:#f4f7fb}h1,h2,h3{color:#123c60}
[data-testid="stMetric"]{background:white;padding:15px;border-radius:9px;border-top:3px solid #168ab5}
[data-testid="stSidebar"]{background:#e7eef5}</style>''',unsafe_allow_html=True)
s = System()
st.sidebar.title('📦 SMART BINS')
st.sidebar.caption('GESTÃO INDUSTRIAL • PROTÓTIPO')
page = st.sidebar.radio('Navegação',['Visão geral','Almoxarifado inteligente','Simulação ESP32','Integração SAP','Histórico de movimentações','Indicadores e acuracidade'])
st.sidebar.info('ESP32 → Middleware → SAP\n\nTodos os dispositivos, pessoas e documentos são simulados.')
if st.sidebar.checkbox('Confirmar restauração completa'):
    if st.sidebar.button('Restaurar estado inicial',type='primary'):
        s.reset()
        st.session_state.pop('last_payload',None)
        st.rerun()
st.title(page)
st.caption('SMART BINS | ESP32 + SAP • Demonstração acadêmica • horários em UTC')
materials = s.materials()
events = s.events()
registered = [e for e in events if e['status']=='REGISTRADO']
pending = [e for e in events if e['status'].startswith('PENDENTE')]


def picture(m):
    if m['photo']:
        st.image(io.BytesIO(m['photo']),width=180)
    elif m['code'] not in ('MAT-0001','MAT-0002'):
        st.info('📷 Envie uma fotografia no cadastro deste material.')
    else:
        st.image(str(Path(__file__).parent/'assets'/('screw.svg' if m['code']=='MAT-0001' else 'washer.svg')),width=180)
        st.caption('Ilustração demonstrativa • massa fictícia')


def run_action(fn):
    try:
        payload = fn()
        if payload:
            st.session_state.last_payload = payload
        st.rerun()
    except Exception as exc:
        st.error(str(exc))


if page=='Visão geral':
    values = [('Materiais',len(materials)),('Unidades no SAP',sum(m['stock'] for m in materials)),
              ('Movimentações',len(registered)),('Entradas',sum(e['kind']=='ENTRADA' for e in registered)),
              ('Saídas',sum(e['kind']=='SAÍDA' for e in registered)),('Eventos pendentes',len(pending)),
              ('Abaixo do mínimo',sum(m['stock']<m['minimum'] for m in materials))]
    cols = st.columns(4)
    for i,(label,value) in enumerate(values):
        cols[i%4].metric(label,value)
    st.subheader('Roteiros para apresentação')
    st.info('Cada cenário restaura o banco antes de executar. O cenário D permanece pendente até recuperar o SAP na página Integração SAP.')
    confirm = st.checkbox('Autorizo restaurar os dados ao executar um cenário')
    for letter,label in [('A','Retirada: 200 → 190 g / saldo 95'),('B','Reposição: 20 → 22 g / saldo 220'),
                         ('C','Medição incompatível / saldo preservado'),('D','SAP indisponível / fila persistente'),('E','Duas pessoas / autoria não confirmada')]:
        if st.button(f'Cenário {letter} — {label}',disabled=not confirm):
            run_action(lambda: s.scenario(letter))
    if events:
        st.subheader('Último resultado')
        st.json({k:v for k,v in events[0].items() if k!='payload'})

elif page=='Almoxarifado inteligente':
    for i,m in enumerate(materials):
        col = st.container()
        with col,st.container(border=True):
            picture(m)
            st.subheader(m['name'])
            st.caption(f"{m['code']} • {m['bin']} • {m['location']}")
            st.metric('Saldo oficial SAP',f"{m['stock']} {m['unit']}")
            st.write(f"Massa líquida: {m['physical']-m['tare']:.3f} g | Bruta: {m['physical']:.3f} g")
            st.write(f"Estimativa por massa: {(m['physical']-m['tare'])/m['unit_weight']:.2f} unidades")
            st.write('🟢 Conectado' if m['connected'] else '🔴 Desconectado')
            if m['stock']<m['minimum']:
                st.warning('Estoque abaixo do mínimo')
            with st.expander('Editar cadastro / fotografia'):
                with st.form('edit'+m['code']):
                    fields = {}
                    for key,label in [('name','Nome'),('description','Descrição'),('category','Categoria'),('unit','Unidade'),('bin','Caixa'),('location','Localização / zona'),('sensor','Sensor')]:
                        fields[key] = st.text_input(label,m[key])
                    for key,label in [('unit_weight','Peso unitário (g)'),('tare','Tara (g)'),('tolerance','Tolerância de estabilidade e resíduo (g)'),('threshold','Limite mínimo de alteração (g)')]:
                        fields[key] = st.number_input(label,min_value=0.,value=float(m[key]),step=.01,format='%.4f')
                    for key,label in [('initial_qty','Quantidade inicial'),('minimum','Estoque mínimo')]:
                        fields[key] = st.number_input(label,min_value=0,value=int(m[key]),step=1)
                    photo = st.file_uploader('Fotografia real (PNG/JPEG, até 5 MB)',type=['png','jpg','jpeg'],key=m['code'])
                    if st.form_submit_button('Salvar cadastro'):
                        try:
                            if photo:
                                from PIL import Image
                                raw = photo.getvalue()
                                if len(raw)>5*1024*1024:
                                    raise ValueError('Imagem acima de 5 MB')
                                Image.open(io.BytesIO(raw)).verify()
                                fields['photo'] = raw
                            s.save_material(m['code'],fields)
                            st.rerun()
                        except Exception as exc:
                            st.error(str(exc))
    with st.expander('Cadastrar outro material'):
        with st.form('new_material'):
            code = st.text_input('Código SAP fictício', 'MAT-0003')
            name = st.text_input('Nome da peça')
            box = st.text_input('Identificação da nova caixa', 'CX-003')
            sensor = st.text_input('Identificação do novo sensor', 'HX711-CX-003')
            location = st.text_input('Zona / localização', 'Zona C')
            weight = st.number_input('Massa unitária (g)',min_value=.001,value=1.,format='%.4f')
            qty = st.number_input('Saldo inicial (unidades)',min_value=0,value=0,step=1)
            tare = st.number_input('Tara da nova caixa (g)',min_value=0.,value=50.)
            minimum = st.number_input('Mínimo (unidades)',min_value=0,value=10,step=1)
            tolerance = st.number_input('Tolerância (g)',min_value=.0001,value=.02,format='%.4f')
            threshold = st.number_input('Limite de alteração (g)',min_value=.0001,value=.04,format='%.4f')
            if st.form_submit_button('Criar material'):
                run_action(lambda: s.add_material(code,name,box,sensor,location,weight,qty,tare,minimum,tolerance,threshold))
    st.warning('A massa de 0,1 g é fictícia. A confiabilidade depende de calibração, resolução, ruído, montagem e testes físicos com HX711 e células de carga reais.')

elif page=='Simulação ESP32':
    st.subheader('Monitoramento dos Sensores — ESP32')
    code = st.selectbox('Caixa', [m['code'] for m in materials],format_func=lambda c: c+' — '+next(m['bin'] for m in materials if m['code']==c))
    m = s.material(code)
    st.write(f"Sensor {m['sensor']} | Referência bruta estável: {m['baseline']:.3f} g | Massa bruta física simulada: {m['physical']:.3f} g")
    st.caption(f"Critério: amplitude das últimas 3 amostras ≤ {m['tolerance']} g. Tara: {m['tare']} g. Limite de alteração: {m['threshold']} g.")
    cols = st.columns(3)
    for i,(label,units) in enumerate([('Retirar 1 unidade',-1),('Retirar 5 unidades',-5),('Retirar 10 unidades',-10),('Repor 5 unidades',5),('Repor 10 unidades',10),('Repor 20 unidades',20)]):
        if cols[i%3].button(label):
            run_action(lambda: s.simulate(code,units))
    if st.button('Simular instabilidade'):
        run_action(lambda: s.simulate(code,unstable=True))
    if st.button('Simular falha de medição'):
        run_action(lambda: s.simulate(code,incompatible=True))
    if st.button('Simular falha de comunicação' if m['connected'] else 'Reconectar ESP32'):
        s.set_connected(code,not m['connected'])
        st.rerun()
    if st.button('Obter novas leituras / estabilizar massa atual'):
        run_action(lambda: s.simulate(code))
    p = st.session_state.get('last_payload')
    if p:
        st.line_chart(pd.DataFrame({'Massa bruta (g)':p['readings']}))
        st.write('Estável:',p['stable'])
        st.code(f"Δm = {p['current_weight']:.4f} − {p['previous_weight']:.4f} = {p['current_weight']-p['previous_weight']:.4f} g")
    st.subheader('Rastreabilidade de Movimentações')
    st.caption('Simulação de eventos do reconhecimento facial existente; nenhuma câmera ou biometria é utilizada. Presenças expiram em cinco minutos.')
    person = st.selectbox('Funcionário',list(EMPLOYEES),format_func=lambda k:EMPLOYEES[k]+' — '+k)
    zone = st.selectbox('Zona',sorted(set(m['location'] for m in materials)))
    confidence = st.slider('Confiança simulada',0.,1.,.99)
    if st.button('Simular entrada / atualizar zona'):
        s.presence(person,zone,confidence)
        st.rerun()
    if st.button('Simular saída de todos'):
        s.clear_people()
        st.rerun()
    st.dataframe(s.people(),width='stretch')

elif page=='Integração SAP':
    a,b,c = st.columns(3)
    a.metric('ESP32', 'Conectado' if all(m['connected'] for m in materials) else 'Desconectado')
    b.metric('Middleware','Pendente' if pending else 'Aprovado / aguardando')
    c.metric('SAP simulado','Disponível' if s.online() else 'Erro: indisponível')
    if st.button('Indisponibilizar SAP' if s.online() else 'Recuperar conexão SAP'):
        s.set_online(not s.online())
        st.rerun()
    if st.button('Reprocessar eventos pendentes SAP'):
        s.retry()
        st.rerun()
    st.caption('Pendências de validação exigem corrigir a causa e obter uma nova leitura. Reenvio do mesmo ID nunca duplica documento ou saldo. Autoria ambígua não bloqueia o estoque.')
    if events:
        eid = st.selectbox('Evento', [e['id'] for e in events])
        e = next(e for e in events if e['id']==eid)
        st.subheader('1. ESP32 → JSON de massas')
        st.json(json.loads(e['payload']))
        st.subheader('2. Middleware → validação')
        st.write({'status':e['status'],'erro':e['error'],'variação_g':e['delta'],'quantidade_inferida':e['quantity'],'tipo':e['kind']})
        st.subheader('3. SAP simulado → documento')
        st.write({'documento':e['document'] or 'Não registrado','responsável':e['employee'],'confiança':e['confidence']})
        if st.button('Reenviar exatamente o mesmo JSON'):
            s.receive(json.loads(e['payload']))
            st.rerun()
    else:
        st.info('Execute uma operação física ou cenário para acompanhar o fluxo.')

elif page=='Histórico de movimentações':
    if events:
        frame = pd.DataFrame(events).drop(columns=['payload'])
        frame = frame.rename(columns={'time':'Data e hora UTC','material':'Material','kind':'Tipo','quantity':'Quantidade','employee':'Funcionário','confidence':'Confiança','status':'Integração','document':'Documento SAP','error':'Alerta'})
        frame['Caixa'] = [json.loads(e['payload'])['bin_id'] for e in events]
        st.dataframe(frame,width='stretch',hide_index=True)
        st.download_button('Exportar histórico CSV',frame.to_csv(index=False).encode('utf-8-sig'),'historico.csv','text/csv')
    else:
        st.info('Nenhum evento registrado.')
else:
    st.subheader('Resultados da simulação')
    st.bar_chart(pd.DataFrame([{'Material':m['name'],'Saldo SAP':m['stock'],'Mínimo':m['minimum']} for m in materials]).set_index('Material'))
    if registered:
        df = pd.DataFrame(registered)
        st.subheader('Entradas e saídas por material (unidades)')
        st.bar_chart(df.pivot_table(index='material',columns='kind',values='quantity',aggfunc='sum',fill_value=0))
        st.subheader('Frequência de movimentações por hora (UTC)')
        df['Hora'] = pd.to_datetime(df['time'],utc=True).dt.floor('h')
        st.bar_chart(df.groupby('Hora').size().rename('Movimentações'))
    st.bar_chart(pd.DataFrame({'Eventos':[len(registered),len(pending)]},index=['Processados','Pendentes']))
    for m in materials:
        if m['stock']<m['minimum']:
            st.warning(m['name']+': abaixo do estoque mínimo')
    st.subheader('Acuracidade com referência física simulada')
    st.caption('Referência gerada pelo atuador físico simulado, independente do saldo SAP. Não constitui medição experimental. Durante falhas ou pendências, divergências são esperadas.')
    for m in materials:
        ref = (m['physical']-m['tare'])/m['unit_weight']
        error = abs(m['stock']-ref)
        accuracy = max(0.,100*(1-error/ref)) if ref>0 else (100. if m['stock']==0 else 0.)
        st.write(f"{m['name']}: referência simulada {ref:.3f}; saldo SAP {m['stock']}; erro absoluto {error:.3f}; acuracidade simulada {accuracy:.2f}%")
s.db.close()
