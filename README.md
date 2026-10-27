# Smart Bins | ESP32 + SAP simulado

Protótipo acadêmico funcional em português para demonstrar movimentações de almoxarifado inferidas por massa. Não necessita de SAP, ESP32, câmera, chaves, serviços pagos ou conexão externa durante a utilização.

## Instalação e execução

Python 3.11 ou 3.12 recomendado. Execute na pasta do projeto:

```bash
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows PowerShell (em vez do comando anterior):
# .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

No ambiente já preparado, na pasta `/workspace/SMS`:

```bash
.venv/bin/python -m streamlit run app.py --server.address 0.0.0.0 --server.port 8501 --server.headless true --browser.gatherUsageStats false
```

O banco `data/smartbins.db` é criado automaticamente no diretório de execução. Inicie sempre na raiz do projeto. Fotografias ficam armazenadas no SQLite e sobrevivem a atualizações da página e reinicializações. O botão de restauração apaga eventos, presenças, fotos e personalizações, recriando os dois materiais iniciais. Os cenários também restauram esses dados, mediante confirmação na interface.

## Estrutura

```text
SMS/
├── app.py                   # Seis páginas Streamlit, cadastro e importação de fotos
├── requirements.txt         # Streamlit, pandas e Altair
├── smartbins/
│   ├── __init__.py
│   ├── core.py              # Simulador, middleware, persistência e adaptador SAP
│   └── presentation.py      # Gráficos e contraste visual
├── assets/
│   ├── screw.svg            # Ilustração demonstrativa, não fotografia real
│   ├── washer.svg
│   └── theme.css            # Identidade visual e ajustes responsivos
├── tests/
│   ├── test_core.py         # Cinco cenários e regras de segurança
│   └── test_ui.py           # Execução das seis páginas e cenário pela interface
└── data/                    # Gerado localmente e ignorado pelo Git
```

## Cadastro e fotografias

| Código | Material | Caixa | Peso unitário | Inicial | Massa líquida | Tara | Mínimo | Zona | Tolerância | Limite |
|---|---|---|---:|---:|---:|---:|---:|---|---:|---:|
| MAT-0001 | Parafuso M4 | CX-001 | 2 g | 100 | 200 g | 50 g | 20 | Zona A | 0,1 g | 0,2 g |
| MAT-0002 | Arruela metálica pequena | CX-002 | 0,1 g | 200 | 20 g | 50 g | 40 | Zona B | 0,02 g | 0,04 g |

Sensores: `HX711-CX-001` e `HX711-CX-002`. Categoria: Fixadores; unidade: UN. Os cartões incluem ilustrações vetoriais locais. Em **Almoxarifado inteligente → Editar cadastro / fotografia**, envie PNG/JPEG de até 5 MB para apresentar a peça real. A fotografia não mede nem identifica automaticamente a massa da peça. Edite o peso unitário conforme a referência escolhida pelo grupo. Também é possível cadastrar outras caixas e materiais.

Alterações de calibração, identificação e saldo inicial são permitidas antes do primeiro evento; depois, restaure a demonstração para evitar reinterpretar o histórico. Nome, descrição, categoria, localização, mínimo e foto continuam editáveis.

## Arquitetura e regras

```text
Atuação física simulada
       ↓ altera somente massa física
ESP32 simulado: 5 amostras por aquisição
       ↓ JSON: event_id, sensor_id, bin_id, timestamp,
         previous_weight, current_weight, stable, readings
Middleware: cadastro + continuidade + estabilidade + resíduo
       ↓ quantidade inferida, tipo e autoria simulada
Fila SQLite persistente
       ↓ reprocessamento idempotente
Adaptador SAP simulado: saldo + documento em transação local
```

O argumento de unidades dos botões pertence somente ao simulador físico. Ele não aparece no JSON ESP32. O middleware calcula `delta = massa atual estável − referência anterior` e `quantidade = round(abs(delta) / peso unitário)`. Sinal positivo é ENTRADA; negativo é SAÍDA.

A estabilidade exige pelo menos três amostras finais com amplitude menor ou igual à tolerância cadastrada. O resíduo entre a massa movimentada e o múltiplo inteiro mais próximo não pode ultrapassar essa tolerância. A tolerância precisa ser positiva e menor que metade do peso unitário. O limite de alteração ignora ruído pequeno. Não há alegação de validação experimental desse algoritmo.

As mensagens usam massa **bruta**. A tara é constante e cancela na diferença. Por isso o cenário A transmite 250 → 240 g, correspondente a **200 → 190 g líquidos**; B transmite 70 → 72 g brutos, correspondente a **20 → 22 g líquidos**.

Erros de medição geram `PENDENTE VALIDAÇÃO`, sem documento ou mudança de saldo oficial. Não se força a aprovação: corrija a causa e adquira novas leituras, ou restaure a demonstração. O evento inválido permanece como evidência histórica. Leituras instáveis podem ser seguidas do botão de nova aquisição estável. Desconectar ESP32 bloqueia novas aquisições até a reconexão.

Movimentos válidos atualizam a referência de massa e ficam em `PENDENTE SAP` quando o SAP está indisponível. O estoque oficial só muda na confirmação pelo adaptador. `retry()` envia a fila em ordem cronológica. Saldo e documento fictício são gravados na mesma transação SQLite. A chave primária do ID do evento impede o reenvio do mesmo JSON de gerar outro movimento. `receive()` é o ponto de entrada do middleware e `retry()` contém o adaptador SAP local; uma futura integração real deve substituir essa fronteira e manter as garantias de idempotência e confirmação.

O sistema não executa um leitor contínuo em segundo plano: cada botão ou aquisição gera uma sequência de amostras. A interface se atualiza a cada interação. Não há nenhuma API externa.

## Roteiro para apresentação

Na **Visão geral**, confirme a restauração e escolha um cenário. Cada cenário é independente, começa nos saldos iniciais e fornece seu próprio conjunto de dados executáveis por `System.scenario()`.

| Cenário | Operação executada | Resultado esperado |
|---|---|---|
| A | Retirar 5 parafusos | 190 g líquidos, saída 5, saldo SAP 95, documento SIM, João |
| B | Repor 20 arruelas | 22 g líquidos, entrada 20, saldo SAP 220, documento SIM, Ana |
| C | Acrescentar massa residual de 0,9 g ao parafuso | Pendente de validação, saldo 100, sem documento |
| D | SAP offline + retirada de 5 parafusos | Massa 190 g, saldo oficial ainda 100, evento na fila |
| E | João e Carlos na Zona A + retirada de 5 | Saldo 95, documento gerado, responsável não confirmado |

Para concluir D, abra **Integração SAP**, clique em **Recuperar conexão SAP** e depois **Reprocessar eventos pendentes SAP**. O saldo passa a 95. Clique novamente em reprocessar e em **Reenviar exatamente o mesmo JSON**: saldo e documento permanecem iguais.

Para uma demonstração manual, na página **Simulação ESP32**, registre as presenças em **Rastreabilidade de Movimentações** e depois use os botões físicos. Uma presença única na zona com confiança ≥ 95%, atualizada há menos de cinco minutos, é associada ao evento. Duas presenças na mesma zona produzem literalmente: “Responsável não confirmado — movimentação pendente de atribuição.” Essa pendência de autoria não bloqueia o movimento válido e não se resolve retroativamente por um novo evento de presença. Não há reconhecimento facial nem rastreamento real.

## Indicadores e acuracidade

Os indicadores de estoque e de entradas/saídas usam somente movimentos confirmados pelo SAP simulado. O histórico também mostra eventos ignorados e inválidos com seus estados. O número de eventos pendentes de integração/validação é separado da autoria não confirmada.

A referência de acuracidade é a massa física mantida pelo simulador, dividida pelo peso unitário, e não o saldo SAP. São exibidos referência, erro absoluto e `max(0, 100 × (1 − erro/referência))`. Para referência zero, resultado é 100% quando saldo zero e 0% caso contrário. Esta é uma métrica didática de concordância de saldo, não uma estimativa estatística da precisão do sensor. Falhas, resíduos e filas offline podem produzir divergências visíveis. Nenhum valor apresentado deve ser descrito como resultado experimental industrial.

## Validação executável

```bash
python -m unittest discover -s tests -v
```

Os testes usam bancos temporários e não apagam os dados do aplicativo. Cobrem A–E, fila persistente após reabrir banco, reenvio idempotente, saldo negativo, instabilidade, limiar, desconexão, limite mínimo e calibração. O teste Streamlit executa as seis páginas e clica no cenário A.

## O que foi implementado e o que exige validação física

**O código executa:** cálculos por diferença de massa, validação, sequência de amostras simuladas, cadastro/fotos, SQLite persistente, filas, duplicidade por ID, indicadores, rastreabilidade simulada e documentos SAP fictícios. Não registra por digitação direta das quantidades no ERP.

**Hipóteses industriais ainda não verificadas:** capacidade/resolução da célula de carga e HX711; calibração e linearidade; ruído elétrico e vibração; temperatura, deriva, tara e cargas excêntricas; dispersão da massa entre peças; distinção entre toque, retirada e reposição simultânea; caixas com material misturado; conectividade e segurança de ESP32; sincronização de relógios; correlação real de acesso facial com zona e horário; integração transacional com SAP e configuração de tipos de movimento reais. Para arruelas de **0,1 g**, a confiabilidade física depende expressamente de calibração e ensaios com sensores reais; a simulação não prova que o hardware terá resolução suficiente.

O protótipo é destinado a demonstração local, com um fluxo operacional por vez. Não implementa autenticação, controle de permissões, redundância, transporte MQTT, trilha inviolável, disponibilidade industrial nem transações distribuídas. Fotos são locais, não serviços de reconhecimento. Uma implantação real precisa de testes, análise de risco operacional e adaptador SAP homologado. Não foram medidos ganhos reais de produtividade ou acuracidade industrial.

## Identidade visual do protótipo

A interface utiliza a paleta aproximada fornecida para o estudo de caso: vermelho `#D32F35`, azul `#3475AD`, grafite `#151515`, branco `#FFFFFF` e cinza `#F4F6F8`. Verde identifica entradas e vermelho identifica saídas, com rótulos textuais para não depender apenas da cor. Não é um produto oficial da SMS Group e não utiliza seu logotipo.

O tema claro está em `.streamlit/config.toml` e os ajustes visuais em `assets/theme.css`. Preserve esses arquivos ao copiar ou exportar o projeto e execute o Streamlit na raiz do repositório para carregar a configuração. Cartões, campos e tabelas usam superfícies claras com texto escuro; a navegação se recolhe e os indicadores/botões se reorganizam em telas estreitas. As tabelas mantêm rolagem interna para preservar todas as colunas.

A revisão foi conferida em Chromium nas seis páginas, em larguras de 1440 e 390 pixels, incluindo cadastro expandido, histórico preenchido e cenários simulados em banco temporário. Os 15 testes funcionais existentes passaram. Essa conferência não substitui testes de acessibilidade completos em todos os navegadores e dispositivos.
