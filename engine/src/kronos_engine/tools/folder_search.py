"""Cómo se busca una carpeta por el nombre con que la pide el usuario.

Desde qué carpetas se parte (las que permitió el usuario), hasta dónde se baja,
cómo se comparan los nombres y cuáles se ofrecen para elegir por el significado.
"""

import difflib
import re
import stat
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from kronos_engine.core.folder_access import DEFAULT_DEPTH, FolderAccess, path_key
from kronos_engine.core.platform import App, Folder, Folders
from kronos_engine.tools.apps import alike, find_app, normalize

# Cómo se nombra cada carpeta en la respuesta, y cómo puede pedirla el usuario.
FOLDERS: Mapping[Folder, tuple[str, tuple[str, ...]]] = {
    Folder.DESKTOP: ("Escritorio", ("Escritorio", "Desktop")),
    Folder.DOCUMENTS: ("Documentos", ("Documentos", "Documents")),
    Folder.DOWNLOADS: ("Descargas", ("Descargas", "Downloads")),
    Folder.PICTURES: ("Imágenes", ("Imágenes", "Fotos", "Pictures")),
    Folder.MUSIC: ("Música", ("Música", "Music")),
    Folder.VIDEOS: ("Videos", ("Videos", "Vídeos")),
    Folder.HOME: ("la carpeta personal", ("Personal", "Usuario", "Perfil", "Home")),
}
# «Abrí la sección Documentos», «mis descargas»: se dicen alrededor del nombre.
FILLER = frozenset({"carpeta", "carpetas", "seccion", "folder", "mi", "mis", "my", "de", "del"})
# Lo que se aclara entre paréntesis no es parte del nombre: «Imágenes (fotos)».
ASIDE = re.compile(r"\([^)]*\)")
# Si no está justo ahí, se busca más adentro, pero no en más de tantas carpetas.
_MAX_SCANNED = 3000
# Las palabras más cortas («web», «app») coinciden con demasiadas carpetas.
_MIN_WORD = 4
# Cuántas veces más tiene que valer la mejor carpeta que la segunda para elegirla.
_CLEAR_WIN = 2
# Windows marca así las carpetas que no se muestran (como «AppData»).
_HIDDEN = stat.FILE_ATTRIBUTE_HIDDEN | stat.FILE_ATTRIBUTE_SYSTEM
# Las arman los programas, no el usuario, y tienen miles de carpetas adentro.
_GENERATED = frozenset({"node_modules", "__pycache__"})
# Cuando no se encuentra, cuántos nombres se le ofrecen al modelo para que elija.
# Con `qwen3:8b` en el equipo del usuario, 80 se eligen en medio segundo y 100
# tardan cinco. Las que no entran son las más profundas y menos parecidas.
_MAX_CANDIDATES = 80
# Las parecidas en las letras van primero: las mejores de cada palabra pedida, y no
# más, porque con una palabra común («web», «proyecto») llenarían la lista.
_SIMILAR_PER_WORD = 3
# Desde qué parecido en las letras un nombre cuenta como parecido.
_CLOSE = 0.5


@dataclass(frozen=True)
class Scope:
    """Hasta dónde se busca: cuántos niveles adentro, y qué carpetas no se miran."""

    depth: int = DEFAULT_DEPTH
    # Las carpetas conocidas que el usuario no permitió (según `path_key`).
    skip: frozenset[str] = frozenset()


_EVERYWHERE = Scope()


def join_names(names: Sequence[str]) -> str:
    """«a, b y c»."""
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + f" y {names[-1]}"


def compact(name: str) -> str:
    """El nombre sin acentos, signos ni espacios: «Work Space» y «work-space» son «workspace»."""
    return normalize(ASIDE.sub(" ", name)).replace(" ", "")


def find_folder(name: str) -> Folder | None:
    """La carpeta conocida pedida, o `None` si no es ninguna de ellas."""
    entries = [
        App(alias, folder.value) for folder, (_, aliases) in FOLDERS.items() for alias in aliases
    ]
    found = find_app(ASIDE.sub(" ", name), entries, ignore=FILLER)
    return Folder(found.id) if found else None


@dataclass(frozen=True)
class Root:
    """Una carpeta de donde se puede partir."""

    path: Path
    name: str  # «Escritorio», «proyectos».
    label: str  # «la carpeta Escritorio», «tu carpeta personal».
    aliases: tuple[str, ...]
    # La carpeta personal no se recorre: contiene a las demás, y a mucho más.
    searched: bool = True


def roots_for(access: FolderAccess, folders: Folders) -> list[Root]:
    roots = [
        Root(
            folders.folder_path(folder),
            name,
            "tu carpeta personal" if folder == Folder.HOME else f"la carpeta {name}",
            aliases,
            searched=folder != Folder.HOME,
        )
        for folder, (name, aliases) in FOLDERS.items()
        if folder in access.known
    ]
    for path in access.extra:
        # La raíz de un disco no tiene nombre: se la llama «D:\».
        name = path.name or str(path)
        roots.append(Root(path, name, f"la carpeta {name}", (name,)))
    return roots


def scope_for(access: FolderAccess, folders: Folders) -> Scope:
    # Una carpeta conocida que no se permitió tampoco se mira desde otra que la
    # contenga, como la carpeta personal.
    skip = frozenset(
        path_key(folders.folder_path(folder)) for folder in Folder if folder not in access.known
    )
    return Scope(access.depth, skip)


def subfolders(path: Path, scope: Scope = _EVERYWHERE) -> list[Path]:
    """Las carpetas que hay adentro y que el usuario ve: sin archivos, ocultas ni prohibidas."""
    try:
        entries = list(path.iterdir())
    except OSError:
        return []
    found: list[Path] = []
    for entry in entries:
        if entry.name.startswith(".") or entry.name in _GENERATED:
            continue
        try:
            info = entry.stat()
            # Un enlace se mira a sí mismo: «Mis vídeos», en Documentos, es un enlace
            # oculto a Videos, aunque Videos no esté oculta.
            hidden = getattr(entry.lstat(), "st_file_attributes", 0) & _HIDDEN
            # Y no lleva a una carpeta prohibida: sería entrar por la ventana.
            target = path_key(entry.resolve()) if entry.is_symlink() or entry.is_junction() else ""
        except OSError:
            continue
        skipped = path_key(entry) in scope.skip or target in scope.skip
        if stat.S_ISDIR(info.st_mode) and not hidden and not skipped:
            found.append(entry)
    return sorted(found, key=lambda entry: entry.name.casefold())


def find_child(name: str, folders: Sequence[Path]) -> Path | None:
    """La subcarpeta pedida, de entre las que hay: se elige de la lista, nunca se arma una ruta."""
    wanted = compact(name)
    if not wanted:
        return None
    # «Work Space» es «Workspace»: la transcripción a veces parte una palabra.
    if same := [path for path in folders if compact(path.name) == wanted]:
        return same[0]
    found = find_app(name, [App(path.name, str(path)) for path in folders], ignore=FILLER)
    return Path(found.id) if found else None


def levels(path: Path, scope: Scope = _EVERYWHERE) -> list[list[Path]]:
    """Las carpetas visibles de cada nivel, hasta `scope.depth` niveles adentro."""
    found: list[list[Path]] = []
    level, scanned = [path], 0
    for _ in range(scope.depth):
        deeper = [child for folder in level for child in subfolders(folder, scope)]
        if not deeper:
            break
        # Una carpeta enorme (como Descargas) no traba la respuesta.
        deeper = deeper[: _MAX_SCANNED - scanned]
        found.append(deeper)
        scanned += len(deeper)
        if scanned >= _MAX_SCANNED:
            break
        level = deeper
    return found


def below(path: Path, scope: Scope = _EVERYWHERE) -> list[Path]:
    """Las carpetas visibles hasta `scope.depth` niveles adentro, primero las más cercanas."""
    return [folder for level in levels(path, scope) for folder in level]


def _same_word(word: str, other: str) -> bool:
    """La misma palabra, o con un error de transcripción («workspase»). El error casi
    nunca cae en la primera letra: sin eso, «ingles» pasaba por «finales»."""
    return word == other or (word[:1] == other[:1] and alike(word, other))


def sharing_a_word(name: str, folders: Sequence[Path]) -> Path | None:
    """La carpeta que comparte con lo pedido las palabras más raras: «Portfolio Web» es
    «Portfolio-master» si no hay otra con «portfolio», y «mi proyecto de Kronos» es
    «kronos-ai-assistant» aunque haya otras con «proyecto», porque «kronos» solo está
    en esa. Si dos quedan parejas, no se adivina."""
    words = {
        word
        for word in normalize(ASIDE.sub(" ", name)).split()
        if len(word) >= _MIN_WORD and word not in FILLER
    }
    names = {path: normalize(path.name).split() for path in folders}
    # Cada palabra vale menos cuantas más carpetas la tienen.
    score: dict[Path, float] = {}
    for word in words:
        hits = [path for path in folders if any(_same_word(word, other) for other in names[path])]
        for path in hits:
            score[path] = score.get(path, 0.0) + 1 / len(hits)
    ranked = sorted(score.items(), key=lambda entry: -entry[1])
    if not ranked:
        return None
    if len(ranked) > 1 and ranked[0][1] < _CLEAR_WIN * ranked[1][1]:
        return None
    return ranked[0][0]


# Cómo se busca, de la más estricta a la más suelta: justo adentro, más adentro,
# y por último por una sola palabra.
_Search = Callable[[str, Path, Scope], Path | None]
SEARCHES: tuple[_Search, ...] = (
    lambda name, root, scope: find_child(name, subfolders(root, scope)),
    lambda name, root, scope: find_child(name, below(root, scope)),
    lambda name, root, scope: (
        sharing_a_word(name, subfolders(root, scope)) or sharing_a_word(name, below(root, scope))
    ),
)


def locate(name: str, root: Path, scope: Scope = _EVERYWHERE) -> Path | None:
    """La carpeta pedida, adentro de `root`: justo ahí o hasta unos niveles más abajo."""
    for search in SEARCHES:
        if found := search(name, root, scope):
            return found
    return None


def _likeness(wanted: str, folder: str) -> float:
    """Cuánto se parece una palabra pedida a alguna del nombre de la carpeta, de 0 a 1."""
    return max(
        (difflib.SequenceMatcher(None, wanted, part).ratio() for part in normalize(folder).split()),
        default=0.0,
    )


def similar(name: str, paths: Sequence[Path]) -> list[int]:
    """Las posiciones de las carpetas más parecidas en las letras, la más parecida primero.

    Cada palabra pedida trae sus mejores: si no, en «el proyecto del cine» las muchas
    carpetas con «proyecto» dejarían afuera a la única con «cine».
    """
    words = [compact(name)] + [
        word for word in normalize(ASIDE.sub(" ", name)).split() if word not in FILLER
    ]
    best: dict[int, float] = {}
    for word in dict.fromkeys(words):
        scores = [
            # La primera «palabra» es el nombre entero, comparado entero.
            difflib.SequenceMatcher(None, word, compact(path.name)).ratio()
            if word == words[0]
            else _likeness(word, path.name)
            for path in paths
        ]
        ranked = sorted(range(len(paths)), key=lambda index: -scores[index])
        for index in [index for index in ranked if scores[index] >= _CLOSE][:_SIMILAR_PER_WORD]:
            best[index] = max(best.get(index, 0.0), scores[index])
    # `sorted` no cambia el orden de los empates: quedan como se recorrieron.
    return sorted(best, key=lambda index: -best[index])


def closest(name: str, bases: Sequence[Path], scope: Scope = _EVERYWHERE) -> list[Path]:
    """Las carpetas para elegir por el significado: primero las que se parecen en las
    letras, después las menos profundas, que son las que el usuario suele nombrar."""
    found: list[tuple[int, Path]] = []
    seen: set[str] = set()
    for base in bases:
        for depth, level in enumerate(levels(base, scope)):
            for path in level:
                if (key := path_key(path)) not in seen:
                    seen.add(key)
                    found.append((depth, path))
    alike_names = similar(name, [path for _, path in found])
    taken = set(alike_names)
    by_depth = sorted(
        (index for index in range(len(found)) if index not in taken),
        key=lambda index: found[index][0],
    )
    return [found[index][1] for index in [*alike_names, *by_depth][:_MAX_CANDIDATES]]
