from hashlib import sha512, sha1
from json import loads
from pathlib import Path
from sys import exit
from time import sleep
from typing import Optional
from zipfile import ZipFile, BadZipFile
from colorama import init, Fore
from requests import get
from tqdm import tqdm
from yaml import safe_load


# Initializing colorama
init(autoreset=True)

# Creating a class to store colors
class Color:
    RESET = Fore.RESET
    RED = Fore.LIGHTRED_EX
    WHITE = Fore.LIGHTWHITE_EX
    GREEN = Fore.LIGHTGREEN_EX
    BLUE = Fore.LIGHTBLUE_EX
    YELLOW = Fore.LIGHTYELLOW_EX
    CYAN = Fore.LIGHTCYAN_EX
    MAGENTA = Fore.LIGHTMAGENTA_EX

class Brackets(Color):
    def __init__(self, color, text, jump_line=False):
        self.color = color
        self.text = text
        self.jump_line = jump_line

    def __str__(self):
        if self.jump_line:
            return f'\n{Fore.WHITE}[{self.color}{self.text}{Fore.WHITE}]{Fore.WHITE}'
        else:
            return f'{Fore.WHITE}[{self.color}{self.text}{Fore.WHITE}]{Fore.WHITE}'


# Creating a class to store the settings
if Path('mcmu-config.yaml').exists():
    with open('mcmu-config.yaml', 'r') as app_config:
        data = safe_load(app_config)

    class AppConfig:
        temp_mods = Path(Path.cwd(), '.temp')
        old_mods = Path(Path.cwd(), 'old_mods')
        corrupted_mods = Path(Path.cwd(), 'corrupted_mods')
        minecraft_dir = data['minecraft_dir']
        mod_version = data['mod_version']
        mod_loader = 'fabric'

def check_jarfile(jarfile_path: Path) -> bool:
    try:
        with ZipFile(jarfile_path, 'r') as zipfile:
            zipfile.testzip()
            return True
    except BadZipFile:
        return False

def get_info_from_jar(jarfile_path: Path) -> Optional[tuple]:
    if AppConfig.mod_loader == 'fabric':
        try:
            with ZipFile(jarfile_path, 'r') as jarfile:
                data = loads(jarfile.read('fabric.mod.json').decode('utf-8'))
                mod_name = data['name']
                dependencies = data['depends']
        except Exception:
            return None
    elif AppConfig.mod_loader == 'forge':
        return None  # TODO: Add forge support
    return mod_name, dependencies

def get_hash_from_file(file_path: Path, hash_type: str) -> str:
    if hash_type == 'sha512':
        with open(file_path, 'rb') as fi:
            file_hash = sha512(fi.read()).hexdigest()
            return file_hash
    elif hash_type == 'sha1':
        with open(file_path, 'rb') as fi:
            file_hash = sha1(fi.read()).hexdigest()
            return file_hash

def modrinth_api_search(query: str):
    search_call = f'https://api.modrinth.com/v2/search?query={query}&limit=1&offset=0&filters=categories="{AppConfig.mod_loader}"&versions=["{AppConfig.mod_version}"]'
    search_resp = get(search_call, allow_redirects=True)
    search_data = search_resp.json()

    if not search_data['hits']:
        print(
            Brackets(Color.RED, 'FINISHED'),
            f'{Color.WHITE}The mod was not found on Modrinth!',
        )
        return False
    slug_name = search_data['hits'][0]['slug']
    return slug_name

def modrinth_api_project(slug_name: str) -> Optional[tuple]:
    project_call = f'https://api.modrinth.com/v2/project/{slug_name}/version?loaders=["{AppConfig.mod_loader}"]&game_versions=["{AppConfig.mod_version}"]'
    project_resp = get(project_call, allow_redirects=True)
    project_data = project_resp.json()

    if not project_data:
        return None
    mod_filename = project_data[0]['files'][0]['filename']
    mod_download_url = project_data[0]['files'][0]['url']
    mod_modrinth_sha512 = project_data[0]['files'][0]['hashes']['sha512']
    mod_modrinth_sha1 = project_data[0]['files'][0]['hashes']['sha1']
    return mod_filename, mod_download_url, mod_modrinth_sha512, mod_modrinth_sha1


# Creating the mcmu-config.yaml file if it doesn't exist
if not Path('mcmu-config.yaml').exists():
    with open('mcmu-config.yaml', 'w') as app_config:
        data = r"minecraft_dir: 'C:\Users\******\AppData\Roaming\.minecraft'  # Directory where .minecraft is located"\
               "\nmod_version: 'x.XX.X'  # Version that will be used to search and update mods"
        app_config.write(data)
    print(
        Brackets(Color.YELLOW, 'INFO', True),
        (
            f'{Color.WHITE}The mcmu-config.yaml file has been successfully created!'
            ' Please configure it before opening the program again!'
        ),
    )
    input()
    exit()

# Checks if minecraft directory exists
if not Path(AppConfig.minecraft_dir).exists():
    print(
        Brackets(Color.RED, 'FINISHED', True),
        f"{Color.WHITE}The directory '{AppConfig.minecraft_dir}' does not exist!",
    )
    input()
    exit()
# Checks if the mods directory exists
if not Path(AppConfig.minecraft_dir + '/mods').exists():
    print(
        Brackets(Color.RED, 'FINISHED', True),
        (
            fr"{Color.WHITE}The mods directory '{AppConfig.minecraft_dir}\mods' does not exist!"
        ),
    )
    input()
    exit()

# Check if the mods directory is empty
if not list(Path(AppConfig.minecraft_dir + '/mods').glob('*.jar')):
    print(
        Brackets(Color.RED, 'FINISHED', True),
        f"{Color.WHITE}The mods directory '{AppConfig.minecraft_dir}\mods' is empty!",
    )
    input()
    exit()

# Check if choosen version is available
available_versions_url = 'https://raw.githubusercontent.com/Henrique-Coder/mc-mods-updater/main/available_versions.txt'
response = get(available_versions_url)
if response.status_code == 200:
    available_versions_str = response.text
    available_versions = available_versions_str.split('\n')
    if AppConfig.mod_version not in available_versions:
        print(
            Brackets(Color.RED, 'FINISHED', True),
            f"{Color.WHITE}The version '{AppConfig.mod_version}' is not available!",
        )
        input()
        exit()
else:
    print(
        Brackets(Color.RED, 'FINISHED', True),
        f'{Color.WHITE}Failed to fetch available versions from URL: {available_versions_url}',
    )
    input()
    exit()

# Inicia o atualizador
dependencies_list = list()
for mod_dir in Path(AppConfig.minecraft_dir + '/mods').glob('*.jar'):
    mod_file = mod_dir.name

    # Mostra o arquivo que está sendo verificado
    print(Brackets(Color.YELLOW, 'INFO', True), f'{Color.WHITE}File: {mod_file}')

    # Verifica se o .jar está corrompido
    print(
        Brackets(Color.BLUE, 'RUNNING'), f'{Color.WHITE}Checking the file is corrupt...'
    )
    if not check_jarfile(mod_dir):
        print(
            Brackets(Color.RED, 'FINISHED'),
            f'{Color.WHITE}The file is corrupt, moving...',
        )
        AppConfig.corrupted_mods.mkdir(exist_ok=True)
        mod_dir.rename(Path(AppConfig.corrupted_mods, mod_file))
        continue
    else:
        print(
            Brackets(Color.BLUE, 'RUNNING'), f'{Color.WHITE}The file is not corrupted!'
        )

    # Pega as informações do mod
    print(Brackets(Color.BLUE, 'RUNNING'), f'{Color.WHITE}Extracting information...')
    jar_info = get_info_from_jar(mod_dir)
    if not jar_info:
        print(
            Brackets(Color.RED, 'FINISHED'),
            f'{Color.WHITE}Unable to extract information from file!',
        )
        continue
    mod_name, dependencies = jar_info
    dependencies_list.extend(
        [
            dependency.split(':')[0]
            for dependency in dependencies
            if dependency.split(':')[0] not in dependencies_list
        ]
    )

    slug_name = modrinth_api_search(mod_name)
    if not slug_name:
        continue
    mod_data = modrinth_api_project(slug_name)
    if not mod_data:
        print(
            Brackets(Color.RED, 'FINISHED'),
            (
                f'{Color.WHITE}The specified version of this mod was not found on Modrinth!'
            ),
        )
        continue
    mod_filename, mod_download_url, mod_modrinth_sha512, mod_modrinth_sha1 = mod_data

    # Verifica se o mod está atualizado
    print(Brackets(Color.BLUE, 'RUNNING'), f'{Color.WHITE}Official name: {mod_name}')
    print(
        Brackets(Color.BLUE, 'RUNNING'),
        f'{Color.WHITE}Required dependencies: {dependencies}',
    )
    print(
        Brackets(Color.BLUE, 'RUNNING'), f"{Color.WHITE}Checking if it's up to date..."
    )
    if mod_modrinth_sha512 == get_hash_from_file(mod_dir, 'sha512'):
        print(Brackets(Color.GREEN, 'FINISHED'), f'{Color.WHITE}The mod is updated!')
        continue
    else:
        print(
            Brackets(Color.BLUE, 'RUNNING'),
            f'{Color.WHITE}Mod is not up to date, downloading latest version...',
        )
        AppConfig.old_mods.mkdir(exist_ok=True)
        AppConfig.temp_mods.mkdir(exist_ok=True)
        mod_dir.rename(Path(AppConfig.old_mods, mod_file))
        with get(mod_download_url, allow_redirects=True, stream=True) as mod_download:
            with open(Path(AppConfig.temp_mods, mod_filename), 'wb') as mod_file:
                progress_bar = tqdm(
                    total=0,
                    unit='it',
                    unit_scale=True,
                    desc=(
                        f'{Color.WHITE}[{Color.BLUE}RUNNING{Color.WHITE}]'
                        f' {Color.WHITE}Download progress'
                    ),
                )
                for data in mod_download.iter_content(chunk_size=1024):
                    mod_file.write(data)
                    progress_bar.update(1)
                progress_bar.close()
        print(
            Brackets(Color.BLUE, 'RUNNING'),
            f"{Color.WHITE}The mod has been successfully downloaded!",
        )
        print(Brackets(Color.BLUE, 'RUNNING'), f'{Color.WHITE}Installing mod...')
        Path(AppConfig.temp_mods, mod_filename).rename(
            Path(AppConfig.minecraft_dir, 'mods', mod_filename)
        )
        print(
            Brackets(Color.GREEN, 'FINISHED'),
            f'{Color.WHITE}The mod has been successfully installed!',
        )
        sleep(0.5)

if AppConfig.temp_mods.exists():
    AppConfig.temp_mods.rmdir()
mod_list = [
    mod_dir.name for mod_dir in Path(AppConfig.minecraft_dir + '/mods').glob('*.jar')
]

print(
    Brackets(Color.GREEN, 'SUCCESS', True),
    f'{Color.WHITE}All mods have been successfully verified/updated!',
)
print(
    Brackets(Color.GREEN, 'SUCCESS'),
    f'{Color.WHITE}Mods installed ({len(mod_list)}): {mod_list}',
)
print(
    Brackets(Color.GREEN, 'SUCCESS'),
    f'{Color.WHITE}Mod dependencies ({len(dependencies_list)}): {dependencies_list}',
)
input()
