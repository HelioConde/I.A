# Auditoria correta dos arquivos GGUF reais, sem regeneração

Run de origem 40653494692 gerou realmente JS usando Ornith 1.5 9B e Qwen3-4B, mas nossa função de limpeza incluiu o banner do novo llama-cli como se fosse código. Reaproveitar arquivos brutos exatos, separar APENAS cabeçalho/prompt/perf, verificar JS e rodar Chromium (teclado, pulo, inimigo) sem editar linhas produzidas pelos modelos. Registrar honestamente todas as falhas.
