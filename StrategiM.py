import os
import requests
from pathlib import Path
from urllib.parse import urljoin
import re


class EstrategiaClient:
    ESTRATEGIA_CONCURSOS_LOGIN_ENDPOINT = "https://api.accounts.estrategia.com/auth/login"
    ESTRATEGIA_MODULES_ENDPOINT = "https://api.estrategia.com/v3/courses/slug/"
    ESTRATEGIA_COURSES_ENDPOINT = "https://api.estrategia.com/v3/courses/catalog?page=1&perPage=1000"

    def __init__(self):
        self.session = requests.Session()

    def authenticate(self, credentials):
        url = self.ESTRATEGIA_CONCURSOS_LOGIN_ENDPOINT
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        
        # Criar parâmetros de formulário
        data = {
            "email": credentials["username"],
            "password": credentials["password"]
        }
        
        # Fazer a requisição POST
        response = self.session.post(url, data=data, headers=headers)
        
        # Verificar se a requisição foi bem-sucedida
        response.raise_for_status()
        
        # Processar a resposta JSON
        response_json = response.json()
        access_token = response_json.get("data", {}).get("token", "")
        
        return access_token


    def get_resources(self, access_token):
        headers = {
            "Authorization": f"Bearer {access_token}",
            "X-Vertical": "militares"
        }
        response = self.session.get(self.ESTRATEGIA_COURSES_ENDPOINT, headers=headers)
        response.raise_for_status()
        return response.json()["data"]


    def get_modules(self, credentials, slug):
        access_token = self.authenticate(credentials)
        headers = {
            "Authorization": f"Bearer {access_token}",
            "X-Vertical": "militares"
        }
        url = urljoin(self.ESTRATEGIA_MODULES_ENDPOINT, slug)
        response = self.session.get(url, headers=headers)
        response.raise_for_status()
        return response.json()["data"]["classes"]

    def get_urls_for_download(self, module_data, download_type):
        download_map = {}
        for module in module_data:
            module_name = module["title"]
            download_map[module_name] = {}
            for content in module["contents"]:
                if content["category"] == "content":
                    file_name = content["name"]
                    if download_type == "pdf" and content["type"] == "pdf":
                        download_map[module_name][f"{file_name}_pdf.pdf"] = content["data"]
                    elif download_type == "video" and content["type"] == "video":
                        download_map[module_name][f"{file_name}_video.mp4"] = content["resolutions"]["720p"]
                    elif download_type == "both":
                        if content["type"] == "pdf":
                            download_map[module_name][f"{file_name}_pdf.pdf"] = content["data"]
                        if content["type"] == "video":
                            download_map[module_name][f"{file_name}_video.mp4"] = content["resolutions"]["720p"]
        return download_map

    def ensure_directory_exists(self, path):
        # Função para garantir que um diretório exista
        if not os.path.exists(path):
            print(f"Criando diretório: {path}")
            os.makedirs(path, exist_ok=True)



    def download_files(self, course_name, download_map, destination_folder):
        sanitized_course_name = self.sanitize_file_name(course_name.strip())
        course_directory = os.path.join(destination_folder, sanitized_course_name)

        self.ensure_directory_exists(course_directory)

        for module_name, files in download_map.items():
            sanitized_module_name = self.sanitize_file_name(module_name.strip())
            module_directory = os.path.join(course_directory, sanitized_module_name)
            print(f"Verificando diretório do módulo: {module_directory}")

            # Verifica se o caminho do diretório do módulo é muito longo e permite que o usuário insira um nome mais curto
            while len(module_directory) > 170:
                print(f"Caminho muito longo: {module_directory}")
                print(f"O nome do módulo '{sanitized_module_name}' é muito longo.")
                new_module_name = self.read_input("Insira um nome mais curto para o módulo: ").strip()
                sanitized_module_name = self.sanitize_file_name(new_module_name)
                module_directory = os.path.join(course_directory, sanitized_module_name)
                self.ensure_directory_exists(module_directory)

            for file_name, file_url in files.items():
                sanitized_file_name = self.sanitize_file_name(file_name.strip())

                if len(sanitized_file_name) > 100:
                    sanitized_file_name = sanitized_file_name[:100]

                # Verifica se o arquivo é um vídeo e adiciona a extensão .mp4, se necessário
                if file_url and file_name.lower().endswith("_video"):
                    if not sanitized_file_name.lower().endswith(".mp4"):
                        sanitized_file_name += ".mp4"

                file_path = os.path.join(module_directory, sanitized_file_name)
                print(f"Verificando caminho do arquivo: {file_path}")

                # Verifica se o caminho do arquivo é muito longo e permite que o usuário insira um nome mais curto
                while len(file_path) > 250:
                    print(f"Caminho muito longo: {file_path}")
                    new_file_name = self.read_input("Insira um nome menor para o arquivo: ").strip()
                    sanitized_file_name = self.sanitize_file_name(new_file_name)
                    if file_url and file_name.lower().endswith("_video"):
                        if not sanitized_file_name.lower().endswith(".mp4"):
                            sanitized_file_name += ".mp4"
                    file_path = os.path.join(module_directory, sanitized_file_name)

                                    # Verifique se o caminho ainda é longo e trunque se necessário
                    if len(file_path) > 260:
                        truncated_file_name = sanitized_file_name[:150]
                        file_path = os.path.join(module_directory, truncated_file_name)


                file_dir = os.path.dirname(file_path)
                self.ensure_directory_exists(file_dir)

                try:
                    if file_url:
                        print(f"Baixando arquivo: {file_url}")
                        with self.session.get(file_url, stream=True) as response:
                            response.raise_for_status()

                            if "pdf" in sanitized_file_name and response.headers.get('Content-Type') != 'application/pdf':
                                print(f"Erro ao baixar PDF: {file_url} - Tipo de conteúdo inválido.")
                                continue

                            with open(file_path, 'wb') as file:
                                for chunk in response.iter_content(chunk_size=8192):
                                    file.write(chunk)
                        print(f"Arquivo baixado: {file_path}")
                    else:
                        print(f"URL do arquivo inválida: {file_url}")
                except requests.RequestException as e:
                    print(f"Erro ao baixar arquivo: {file_url}")
                    print(e)

            print(f"Renomeando vídeos no módulo: {module_name}")
            self.rename_videos(module_directory)

    def rename_videos(self, directory):
        # Verificar se o diretório existe
        if not os.path.exists(directory):
            print(f"Erro: O diretório {directory} não existe.")
            return
        
        # Verifica se o diretório está vazio
        if not os.listdir(directory):
            print(f"Ignorando o diretório vazio: {directory}")
            return
        
        # Lista todos os arquivos no diretório
        files = [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]
        
        # Filtra apenas os arquivos de vídeo (extensões comuns de vídeos)
        video_extensions = ('.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv')
        video_files = [f for f in files if f.lower().endswith(video_extensions)]
        
        # Ordena os arquivos pela data de modificação (do mais antigo para o mais recente)
        video_files.sort(key=lambda f: os.path.getmtime(os.path.join(directory, f)))

        if not video_files:
            print(f"Nenhum vídeo encontrado no diretório: {directory}")
            return

        # Renomeia os arquivos adicionando um número sequencial no início
        for index, file_name in enumerate(video_files, start=1):
            old_path = os.path.join(directory, file_name)

            new_file_name = f"{index}. {file_name}"
            new_path = os.path.join(directory, new_file_name)

            # Renomeia o arquivo
            try:
                os.rename(old_path, new_path)
                print(f"Renomeado: {old_path} -> {new_path}")
            except FileNotFoundError as e:
                print(f"Erro ao renomear o arquivo: {e}")

    
    def sanitize_file_name(self, file_name):
        # Remove caracteres inválidos para sistemas de arquivos no Windows
        sanitized_name = re.sub(r'[<>:"/\\|?*]', '_', file_name)
        return sanitized_name


    @staticmethod
    def read_input(prompt):
        return input(prompt).strip()

    @staticmethod
    def print_options(items, include_all_option=False):
        for i, item in enumerate(items, start=1):
            print(f"{i}. {item['title']}")
        if include_all_option:
            print(f"{len(items) + 1}. Todos os módulos")
        print(f"{len(items) + (2 if include_all_option else 1)}. Sair")

    @staticmethod
    def choose_option(items, include_all_option=False):
        while True:
            try:
                choice = int(input("Escolha uma opção: "))
                if 1 <= choice <= len(items):
                    return items[choice - 1]
                elif include_all_option and choice == len(items) + 1:
                    return "all"  # Option to download all modules
                elif choice == len(items) + (2 if include_all_option else 1):
                    return None  # Option to exit
                else:
                    print("Opção inválida. Tente novamente.")
            except ValueError:
                print("Entrada inválida. Por favor, insira um número.")

    @staticmethod
    def choose_download_option():
        while True:
            print("Deseja baixar:")
            print("1. PDFs")
            print("2. Vídeos")
            print("3. Ambos")
            try:
                choice = int(input("Escolha uma opção: "))
                if 1 <= choice <= 3:
                    return ["pdf", "video", "both"][choice - 1]
                else:
                    print("Opção inválida. Tente novamente.")
            except ValueError:
                print("Entrada inválida. Por favor, insira um número.")

def print_banner():
    # Sequências de escape ANSI para cor roxa (magenta)
    BANNER_COLOR = '\033[45m'  # Fundo roxo
    TEXT_COLOR = '\033[97m'    # Texto branco
    RESET_COLOR = '\033[0m'    # Resetar cor

    banner_text = "MAKHRINA"
    banner_length = len(banner_text) + 4
    print(f"{BANNER_COLOR}{TEXT_COLOR}{' ' * banner_length}")
    print(f"{BANNER_COLOR}{TEXT_COLOR}  {banner_text}  {RESET_COLOR}")
    print(f"{BANNER_COLOR}{TEXT_COLOR}{' ' * banner_length}{RESET_COLOR}")

def main():

    # Limpar o terminal
    os.system('cls' if os.name == 'nt' else 'clear')

    # Imprimir cabeçalho personalizado
    print("\033[35m")  # Define a cor roxa
    print("Feito Por:")
    print("")
    print("  ██      ██║  █████║  ██╗    ██║██   ██║ ██████╗  ██║ ██     ██║  █████║ ")
    print("  ████╗  ███║ ██   ██╗ ██║   ██║ ██╗  ██╗ ██╔══██║ ██╗ ███╗   ██║ ██   ██╗ ")
    print("  ██╔████╔██║ ███████║ ██████║   ███████║ ██████║  ██║ ██╔██╗ ██║ ███████║ ")
    print("  ██║╚██╔╝██║ ██╔══██║ ██╔══██║  ██╔══██║ ██╔  ██║ ██║ ██║╚██╗██║ ██╔══██║ ")
    print("  ██║ ╚═╝ ██║ ██   ██║ ██║   ██║ ██║  ██║ ██║  ██║ ██║ ██║ ╚████║ ██   ██║ ")
    print("  ╚═╝     ╚═╝ ╚═╝  ╚═╝ ╚═╝   ╚═╝ ╚═╝  ╚═╝ ╚═╝  ╚═╝ ╚═╝ ╚═╝  ╚═══╝ ╚═╝  ╚═╝  ")
    print("")
    print("")
    print("Acesse: t.me/romanempire1889")

    print("\033[0m")  # Resetar a cor do texto


    client = EstrategiaClient()

    email = client.read_input("Digite seu email: ")
    password = client.read_input("Digite sua senha: ")
    credentials = {"username": email, "password": password}

    access_token = client.authenticate(credentials)
    resources = client.get_resources(access_token)
    
    print("Cursos disponíveis:")
    client.print_options(resources, include_all_option=False)
    
    chosen_course = client.choose_option(resources, include_all_option=False)
    if chosen_course is None:
        print("Saindo...")
        return

    course_name = chosen_course["title"]
    slug = chosen_course["slug"]

    modules = client.get_modules(credentials, slug)
    print("Módulos do curso selecionado:")
    client.print_options(modules, include_all_option=True)

    chosen_module = client.choose_option(modules, include_all_option=True)
    if chosen_module is None:
        print("Saindo...")
        return

    if chosen_module == "all":
        download_map = client.get_urls_for_download(modules, client.choose_download_option())
    else:
        module_name = chosen_module["title"]
        selected_module = next(module for module in modules if module["title"] == module_name)
        download_map = client.get_urls_for_download([selected_module], client.choose_download_option())

    pasta_destino = client.read_input("Escolha a pasta de Destino(/tmp é a pasta padrão): ") or "/tmp/"
    
    if not download_map:
        print("Opção não tem arquivos para baixar! Tente outra opção!")
    else:
        client.download_files(course_name, download_map, pasta_destino)

if __name__ == "__main__":
    main()
