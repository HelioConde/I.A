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
                task=input("Descreva a mecanica JavaScript que deseja criar: ").strip()
                if task:
                    run(HERE/"luna_coder_ollama.py","generate","--task",task)
        else:
            print("Opcao invalida.")

if __name__=="__main__":
    try:
        sys.exit(main())
    except (EOFError, KeyboardInterrupt):
        print("\nEncerrando.")
