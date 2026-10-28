"""Menu local para Luna Forge; executa adaptadores existentes, nunca codigo gerado."""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime

HERE=Path(__file__).resolve().parent
BRIDGE=HERE/"brain_ssd_bridge.py"

def run(*args) -> int:
    process=subprocess.run([sys.executable,*map(str,args)],cwd=HERE,check=False)
    return process.returncode

def local_status() -> int:
    return run(BRIDGE,"status")

def plan(prompt: str) -> int:
    return run(BRIDGE,"plan","--request",prompt)

def code(prompt: str) -> int:
    return run(BRIDGE,"code","--request",prompt,"--max-chars","120")

def train_external() -> int:
    """Treinamento somente com codigos externos MIT e exemplos originais Luna."""
    if run(HERE/"grandchase_reference_gate.py","audit"): return 1
    if run(HERE/"original_lua_lessons.py","verify"): return 1
    data=HERE/"external_data"
    if not (data/"manifest.json").is_file():
        if run(HERE/"github_corpus.py","collect","--out",data): return 1
    if run(HERE/"github_corpus.py","verify","--out",data): return 1
    out=data/("local-candidate-"+datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
    if run(HERE/"train_github.py","--data",data,"--curriculum",
           HERE/"action_platform_curriculum.json","--out",out,
           "--steps","180","--batch","12","--threads","4","--lua-lessons"): return 1
    if run(HERE/"evaluate_github_codegen.py","--checkpoint",out,"--out",
           out/"syntax_report.json"): return 1
    print("Checkpoint experimental:",out)
    print("Nada foi promovido para a Luna principal.")
    return 0

def main():
    while True:
        print("\n=== LUNA FORGE LOCAL / Brain-SSD ===")
        print("1 - Verificar os modelos")
        print("2 - Planejar um jogo (Planner)")
        print("3 - Testar MiniCoder inicial (sem pesos do candidato)")
        print("4 - Treinar candidato (MIT + exemplos Lua/JS originais; opt-in)")
        print("5 - Inventariar pasta local (somente metadados; sem treinar)")
        print("6 - Analisar formatos dos arquivos Lua (somente amostra, sem treinar)")
        print("7 - Resumir estruturas do Lua (funcoes/condicoes/lacos, sem treinar)")
        print("8 - Testar ultimo candidato treinado (somente visualizar codigo)")
        print("9 - GameCoder pratica (Ollama local + validar sintaxe JavaScript)")
        print("10 - Treinar Luna MiniCoder com Lua local autorizado (experimental/privado)")
        print("11 - Testar MiniCoder treinado com Lua privado (sem executar codigo)")
        print("12 - Contar Lua nas pastas excluidas (SOMENTE metadados, sem treino)")
        print("13 - Revisar subpastas de cliente/jogo LOCALMENTE (metadados, sem treino)")
        print("14 - Verificar formatos de Lua na pasta Elsword (4 KiB por arquivo, sem treino)")
        print("15 - Medir geracao Lua da Luna propria em 3 tarefas originais nao treinadas")
        print("16 - TREINAR Luna Lua V2 do zero (somente 6 mecanicas originais)")
        print("17 - Comparar Luna Lua V2 em 3 tarefas novas (sem executar codigo)")
        print("18 - Diagnosticar Luna V2 (greedy, memoria de treino, sintaxe luac opcional)")
        print("0 - Sair")
        option=input("Opcao: ").strip()
        if option=="0":
            return 0
        if option=="1":
            local_status()
        elif option=="2":
            prompt=input("Descreva o jogo: ").strip()
            if prompt: plan(prompt)
        elif option=="3":
            prompt=input("Descreva a tarefa de codigo: ").strip()
            if prompt:
                print("Saida nao validada. Nao execute codigo gerado sem revisao.")
                code(prompt)
        elif option=="4":
            confirm=input("Confirmar treinamento com MIT + Lua original (sem Grand Chase)? Digite SIM: ").strip()
            if confirm.upper()=="SIM": train_external()
            else: print("Cancelado.")
        elif option=="5":
            default_folder=Path.home()/"Documents"/"grand chase files"
            supplied=input(f"Pasta para analisar [{default_folder}]: ").strip().strip('"')
            folder=Path(supplied) if supplied else default_folder
            if not folder.is_dir():
                print("Pasta nao encontrada. Nenhum arquivo alterado.")
            else:
                destination=HERE/"reports"/("local_inventory-"+datetime.now().strftime("%Y%m%d-%H%M%S-%f")+".json")
                print("Lendo apenas nomes, extensoes e tamanhos. Nao abre os arquivos.")
                run(HERE/"inventory_local_data.py",folder,"--out",destination)
                print("Relatorio local:",destination)
        elif option=="6":
            default_folder=Path.home()/"Documents"/"grand chase files"
            supplied=input(f"Pasta para verificar arquivos Lua [{default_folder}]: ").strip().strip('"')
            folder=Path(supplied) if supplied else default_folder
            if not folder.is_dir():
                print("Pasta nao encontrada. Nada alterado.")
            else:
                destination=HERE/"reports"/("lua_format_audit-"+datetime.now().strftime("%Y%m%d-%H%M%S-%f")+".json")
                print("Apenas 4 KB iniciais por arquivo .lua. Sem guardar codigo e sem treinar.")
                rc=run(HERE/"analyze_local_lua.py",folder,"--out",destination)
                if rc==0: print("Relatorio local:",destination)
        elif option=="7":
            default_folder=Path.home()/"Documents"/"grand chase files"
            supplied=input(f"Pasta para perfil estrutural Lua [{default_folder}]: ").strip().strip('"')
            folder=Path(supplied) if supplied else default_folder
            if not folder.is_dir():
                print("Pasta nao encontrada. Nada alterado.")
            else:
                destination=HERE/"reports"/("lua_structure-"+datetime.now().strftime("%Y%m%d-%H%M%S-%f")+".json")
                print("Somente contagens agregadas, ate 64 KiB por Lua. Nenhum codigo salvo ou treinado.")
                rc=run(HERE/"profile_local_lua.py",folder,"--out",destination)
                if rc==0: print("Relatorio local:",destination)
        elif option=="8":
            print("O candidato NÃO substitui a Luna. O codigo gerado nao sera executado.")
            task=input("Qual funcao JavaScript original a GameCoder deve tentar criar? ").strip()
            if task:
                run(HERE/"preview_local_candidate.py","generate","--task",task,"--chars","180")
        elif option=="9":
            print("Usa modelo de codigo pre-treinado LOCAL no Ollama, nao os 116K pesos do MiniCoder.")
            print("Nenhum arquivo e enviado, executado ou alterado. Node.js verifica apenas a sintaxe.")
            rc=run(HERE/"luna_coder_ollama.py","status")
            if rc==0:
                print("Modelo opcional: Enter = qwen2.5-coder:3b; 2 = qwen3.5:4b (se instalado).")
                chosen=input("Escolha [Enter/2]: ").strip()
                model="qwen3.5:4b" if chosen=="2" else "qwen2.5-coder:3b"
                task=input("Descreva a mecanica JavaScript que deseja criar: ").strip()
                if task:
                    run(HERE/"luna_coder_ollama.py","generate","--model",model,"--task",task)
        elif option=="10":
            print("ATENCAO: Scripts comerciais podem ter direitos autorais e dados privados.")
            print("Treinar localmente nao concede direitos sobre o codigo. Nao compartilhe os pesos privados.")
            print("Somente .lua UTF-8 em amostra limitada; backups, executaveis, arquivos comprimidos e pastas sensiveis sao excluidos.")
            folder=Path.home()/"Documents"/"grand chase files"
            supplied=input(f"Pasta [Enter = {folder}]: ").strip().strip('"')
            if supplied:
                folder=Path(supplied)
            consent=input("Confirma que revisou a procedencia e tem direitos/permissao para TREINAR localmente esses scripts? Digite TENHO DIREITOS: ").strip()
            if consent.upper()=="TENHO DIREITOS":
                rc=run(HERE/"train_private_lua.py","dry-run","--source",folder,"--acknowledge-rights")
                if rc==0:
                    print("O dry-run acima mostrou somente contagens, sem exportar conteudo.")
                    final=input("Iniciar treino PRIVADO experimental (64 MiB amostrados, 300 passos)? Digite TREINAR: ").strip()
                    if final.upper()=="TREINAR":
                        run(HERE/"train_private_lua.py","train","--source",folder,"--acknowledge-rights","--max-mib","64","--steps","300")
                    else:
                        print("Treinamento cancelado. Nenhum peso alterado.")
            else:
                print("Sem confirmacao de direitos, o treino nao foi iniciado.")
        elif option=="11":
            print("Somente modelo privado da Luna, NAO Qwen. Codigo gerado NAO sera executado.")
            task=input("Qual mecanica Lua deseja que ela tente criar? ").strip()
            if task:
                run(HERE/"preview_private_lua.py","generate","--task",task)
        elif option=="12":
            source=Path.home()/"Documents"/"grand chase files"
            supplied=input(f"Pasta para contagem de metadados [{source}]: ").strip().strip('"')
            if supplied:
                source=Path(supplied)
            print("Contando extensoes em diretorios protegidos SEM abrir arquivos.")
            print("O resultado mostra somente totais, nao nomes, caminhos ou codigo.")
            run(HERE/"audit_excluded_lua_metadata.py",source)
        elif option=="13":
            root=Path.home()/"Documents"/"grand chase files"
            supplied=input(f"Pasta para revisar localmente [{root}]: ").strip().strip('"')
            if supplied:
                root=Path(supplied)
            print("Mostrando caminhos APENAS neste terminal para sua revisao de procedencia/licenca.")
            print("Nenhum codigo sera lido, executado, exportado ou treinado.")
            run(HERE/"review_local_lua_scopes.py","--source",root)
        elif option=="14":
            root=Path.home()/"Documents"/"grand chase files"/"Elsword"
            supplied=input(f"Diretorio Elsword para auditoria [{root}]: ").strip().strip('"')
            if supplied:
                root=Path(supplied)
            print("Somente assinaturas dos primeiros 4 KiB por Lua; nenhum arquivo salvo ou enviado.")
            print("Pastas de backup, contas, credenciais e anti-cheat permanecem excluidas.")
            run(HERE/"audit_elsword_lua_headers.py","--source",root)
        elif option=="15":
            print("Teste da MiniCoder PROPRIA ja treinada; nao usa Qwen nem scripts comerciais.")
            print("As tarefas nao tem respostas no conjunto de treino. A avaliacao NAO verifica sintaxe nem gameplay.")
            print("Nao altera os pesos nem executa codigo gerado.")
            run(HERE/"benchmark_original_lua.py")
        elif option=="16":
            print("Treina NOVOS pesos V2 a partir do zero usando apenas 6 mecanicas LUA originais.")
            print("Modelo experimental (~1M parametros, janela 256), nao altera a Luna atual.")
            print("Nao le pasta Elsword e nao utiliza codigo comercial. Salva pesos localmente.")
            confirm=input("Iniciar 600 passos de treino CPU? Digite TREINAR V2: ").strip()
            if confirm.upper()=="TREINAR V2":
                run(HERE/"train_original_lua_v2.py","--steps","600","--batch","4","--threads","4")
            else:
                print("Treinamento V2 cancelado.")
        elif option=="17":
            print("Testa ultimos pesos V2 locais nos 3 desafios originais SEM respostas.")
            print("Nao verifica sintaxe nem gameplay e nunca executa o codigo produzido.")
            run(HERE/"benchmark_original_lua_v2.py")
        elif option=="18":
            print("Diagnostico V2: gera codigo com escolha deterministica e compara tarefa treinada vs nao treinada.")
            print("Tenta verificar SINTAXE via luac -p (sem executar). Sem luac, reporta indisponivel.")
            print("Nao altera pesos, nao le Elsword nem executa o codigo gerado.")
            run(HERE/"benchmark_original_lua_v2.py",
                "--decode","greedy","--calibrate","--syntax","--chars","240")
        else:
            print("Opcao invalida.")

if __name__=="__main__":
    try:
        sys.exit(main())
    except (EOFError, KeyboardInterrupt):
        print("\nEncerrando.")
