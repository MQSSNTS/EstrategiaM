import os
import requests
from pathlib import Path
from urllib.parse import urljoin

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

    def download_files(self, course_name, download_map, destination_folder):
        sanitized_course_name = self.sanitize_file_name(course_name)
        course_directory = os.path.join(destination_folder, sanitized_course_name)
        
        # Verificar se o diretório do curso existe
        if not os.path.exists(course_directory):
            print(f"Criando diretório: {course_directory}")
            os.makedirs(course_directory, exist_ok=True)

        for module_name, files in download_map.items():
            sanitized_module_name = self.sanitize_file_name(module_name)
            module_directory = os.path.join(course_directory, sanitized_module_name)
            
            # Verificar se o diretório do módulo existe
            if not os.path.exists(module_directory):
                print(f"Criando diretório: {module_directory}")
                os.makedirs(module_directory, exist_ok=True)

            for file_name, file_url in files.items():
                sanitized_file_name = self.sanitize_file_name(file_name)
                file_path = os.path.join(module_directory, sanitized_file_name)
                
                # Verificar comprimento do caminho
                if len(file_path) > 260:  # Limite comum para caminhos em Windows
                    print(f"Caminho muito longo: {file_path}")
                    print(f"Recomendamos você renomear essa pasta caso queira seguir com o download /isso acontece pq o nome da pasta é muito longo/ '{sanitized_module_name}'.")
                    new_module_name = self.read_input("Insira o novo nome da pasta: ")
                    new_module_name = self.sanitize_file_name(new_module_name)
                    module_directory = os.path.join(course_directory, new_module_name)
                    if not os.path.exists(module_directory):
                        print(f"Criando diretório: {module_directory}")
                        os.makedirs(module_directory, exist_ok=True)
                    file_path = os.path.join(module_directory, sanitized_file_name)
                    
                try:
                    # Verificar se a URL do arquivo é válida antes de tentar o download
                    if file_url:
                        with self.session.get(file_url, stream=True) as response:
                            response.raise_for_status()
                            
                            # Verificar o tipo de conteúdo para PDFs
                            if "pdf" in sanitized_file_name and response.headers.get('Content-Type') != 'application/pdf':
                                print(f"Erro ao baixar PDF: {file_url} - Tipo de conteúdo inválido.")
                                continue
                            
                            # Garantir que o diretório do arquivo exista
                            file_dir = os.path.dirname(file_path)
                            if not os.path.exists(file_dir):
                                print(f"Criando diretório: {file_dir}")
                                os.makedirs(file_dir, exist_ok=True)
                            
                            # Baixar o arquivo
                            with open(file_path, 'wb') as file:
                                for chunk in response.iter_content(chunk_size=8192):
                                    file.write(chunk)
                        print(f"Arquivo baixado: {file_path}")
                    else:
                        print(f"URL do arquivo inválida: {file_url}")
                except requests.RequestException as e:
                    print(f"Erro ao baixar arquivo: {file_url}")
                    print(e)

    def sanitize_file_name(self, name, max_length=255):
        invalid_chars = '<>:\"/\\|?*'  # Caracteres inválidos em caminhos de arquivos
        sanitized_name = "".join(c if c.isalnum() or c in " ._-" else "_" for c in name).strip()
        sanitized_name = "".join(c if c not in invalid_chars else "_" for c in sanitized_name)
        # Truncar o nome se exceder o comprimento máximo
        if len(sanitized_name) > max_length:
            sanitized_name = sanitized_name[:max_length]
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


