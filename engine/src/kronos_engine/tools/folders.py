"""Acción: abrir una carpeta que el usuario le permite mirar a Kronos, o una de sus subcarpetas.

Las carpetas permitidas (las conocidas, como Documentos, y las que sumó el
usuario) se eligen en la pestaña Permisos. Fuera de ellas no se busca nada.
Cómo se busca está en `folder_search`.
"""

import asyncio
import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kronos_engine.core.choosing import Chooser
from kronos_engine.core.folder_access import FolderAccess, path_key
from kronos_engine.core.platform import App, Folder, Folders
from kronos_engine.core.tools import PermissionLevel, ToolError, ToolSpec
from kronos_engine.tools.apps import find_app
from kronos_engine.tools.folder_search import (
    ASIDE,
    FILLER,
    FOLDERS,
    SEARCHES,
    Root,
    Scope,
    closest,
    compact,
    find_folder,
    locate,
    roots_for,
    scope_for,
)

log = logging.getLogger(__name__)

_NO_ACCESS = (
    "El usuario no le dio permiso a Kronos para mirar {where}. "
    "Lo puede cambiar en la pestaña Permisos de la configuración."
)


def _join(names: Sequence[str]) -> str:
    """«a, b y c»."""
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + f" y {names[-1]}"


@dataclass(frozen=True)
class _Target:
    path: Path
    label: str  # «la carpeta Workspace, en Escritorio».
    # Lo pedido que no coincidió exacto con el nombre de la carpeta.
    guessed: tuple[str, ...] = ()


# Una carpeta que podría ser la pedida, y dónde está («workspace», «Documentos»).
_Candidate = tuple[Path, str]


class _NotFound(ToolError):
    """No está la subcarpeta número `step` del camino pedido.

    El mensaje es el que recibe el modelo, sin la lista de carpetas: la leería en
    voz alta. Las que podrían ser se calculan recién si se van a usar.
    """

    def __init__(
        self,
        step: int,
        name: str,
        where: str,
        last: bool,
        candidates: Callable[[], list[_Candidate]],
    ) -> None:
        super().__init__(
            f"No hay ninguna carpeta que se llame «{name}» en {where}. "
            "Preguntale al usuario cómo se llama o en qué carpeta está."
        )
        self.step = step
        self.name = name
        # Si es la última del camino: solo entonces se puede elegir una parecida.
        self.last = last
        self.candidates = candidates


class OpenFolderTool:
    level = PermissionLevel.NORMAL

    def __init__(
        self,
        folders: Folders,
        access: Callable[[], FolderAccess] = FolderAccess,
        chooser: Chooser | None = None,
    ) -> None:
        self._folders = folders
        # Se pide en cada uso: el usuario cambia los permisos sin reiniciar el motor.
        self._access = access
        # Elige por el significado cuando no se encuentra por las palabras.
        self._chooser = chooser

    @property
    def spec(self) -> ToolSpec:
        access = self._access()
        roots = roots_for(access, self._folders)
        known = _join([root.name for root in roots]) if roots else "ninguna por ahora"
        pictures = " Las fotos están en Imágenes." if Folder.PICTURES in access.known else ""
        return ToolSpec(
            "open_folder",
            "Abre en el explorador de archivos una de las carpetas que el usuario le permite "
            f"mirar a Kronos ({known}) o una subcarpeta que esté adentro de ellas, a cualquier "
            f"profundidad.{pictures} No abre archivos (para eso está open_file) ni carpetas de "
            "otros lugares. "
            "Aunque no sepas cómo se llama exactamente ni dónde está, usala con lo que "
            "dijo el usuario («mi proyecto de la facultad»), sin preguntarle antes: la "
            "acción la busca también por el significado. Si el usuario dice «carpeta», "
            "es esta acción y no open_app, aunque sea la carpeta de una aplicación o de "
            "un proyecto («la carpeta de la app de recetas»). "
            "Para seguir bajando desde una carpeta ya abierta, pasá el camino completo "
            "desde la carpeta de partida.",
            {
                "type": "object",
                "properties": {
                    "folder": {
                        "type": "string",
                        "description": (
                            f"La carpeta de donde se parte: {known}. Vacío si el usuario "
                            "no dijo dónde está la subcarpeta."
                        ),
                    },
                    "subfolders": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Las subcarpetas por las que hay que entrar, en orden y tal como las "
                            "dijo el usuario. Para «la carpeta Workspace del escritorio»: folder "
                            "Escritorio y subfolders [Workspace]. Vacío para abrir solo la "
                            "carpeta."
                        ),
                    },
                },
            },
        )

    async def describe(self, arguments: Mapping[str, Any]) -> str:
        target = await self._target(arguments)
        return f"abrir {target.label}"

    async def locate(self, arguments: Mapping[str, Any]) -> tuple[Path, str]:
        """La carpeta pedida y cómo nombrarla, sin abrirla: la usa `open_file`."""
        target = await self._target(arguments)
        return target.path, target.label

    async def run(self, arguments: Mapping[str, Any]) -> str:
        target = await self._target(arguments)
        await asyncio.to_thread(self._folders.open_path, target.path)
        # Sin el nombre: el registro no guarda qué carpetas tiene el usuario.
        log.info("Se abrió una carpeta del usuario.")
        result = f"Se abrió {target.label}."
        if target.guessed:
            # El usuario tiene que saber qué se abrió de verdad.
            asked = ", ".join(f"«{name}»" for name in target.guessed)
            result += (
                f" No había ninguna que se llamara exactamente {asked}: decile al usuario "
                f"el nombre de la que se abrió, «{target.path.name}»."
            )
        return result

    async def _target(self, arguments: Mapping[str, Any]) -> _Target:
        try:
            return await asyncio.to_thread(self._find, arguments)
        except _NotFound as missing:
            if self._chooser is None or not missing.last:
                raise
            # Segunda pasada: «mi web personal» es «Portfolio-master». La lista va en
            # una pregunta aparte, nunca en la conversación.
            candidates = await asyncio.to_thread(missing.candidates)
            options = [f"{path.name} (en {place})" for path, place in candidates]
            index = await self._chooser.choose(missing.name, options)
            if index is None:
                raise
            log.info("La carpeta se eligió por el significado.")
            path, place = candidates[index]
            return _Target(path, f"la carpeta {path.name}, en {place}", (missing.name,))

    def _find(self, arguments: Mapping[str, Any]) -> _Target:
        access = self._access()
        roots, scope = roots_for(access, self._folders), scope_for(access, self._folders)
        name = str(arguments.get("folder") or arguments.get("name") or "").strip()
        raw = arguments.get("subfolders") or []
        steps = (
            [str(step).strip() for step in raw if str(step).strip()]
            if isinstance(raw, list)
            else []
        )
        if not name and not steps:
            raise ToolError("Falta el nombre de la carpeta.")
        if not name:
            return self._search(steps, roots, scope)
        root = self._root_named(name, roots, access)
        if root is None:
            if steps:
                places = _join([r.name for r in roots]) if roots else "ninguna"
                raise ToolError(f"No puedo abrir «{name}». Puedo partir de: {places}.")
            # «Abrí Workspace»: puede ser una subcarpeta dicha sin decir dónde está.
            return self._search([name], roots, scope)
        try:
            return self._descend(root, steps, scope)
        except _NotFound as missing:
            # El modelo a veces adivina dónde está («Documentos») sin que el usuario
            # lo haya dicho: se la busca en las demás antes de rendirse.
            if missing.step > 0:
                raise
            return self._search(steps, roots, scope, also=root)

    def _root_named(self, name: str, roots: Sequence[Root], access: FolderAccess) -> Root | None:
        entries = [
            App(alias, str(index)) for index, root in enumerate(roots) for alias in root.aliases
        ]
        if found := find_app(ASIDE.sub(" ", name), entries, ignore=FILLER):
            return roots[int(found.id)]
        folder = find_folder(name)
        if folder is not None and folder not in access.known:
            raise ToolError(_NO_ACCESS.format(where=f"en {FOLDERS[folder][0]}"))
        return None

    def _descend(self, root: Root, steps: Sequence[str], scope: Scope) -> _Target:
        path, here = root.path, root.label
        guessed: list[str] = []
        for index, step in enumerate(steps):
            child = locate(step, path, scope)
            if child is None:
                last = index == len(steps) - 1
                raise _NotFound(
                    index, step, here, last, self._candidates(step, [path], scope, [root])
                )
            if compact(step) != compact(child.name):
                guessed.append(step)
            path, here = child, f"la carpeta {child.name}"
        if not steps or (not root.searched and path.parent == root.path):
            return _Target(path, here, tuple(guessed))
        # Dónde quedó: la carpeta de partida o la subcarpeta que la contiene.
        parent = root.name if path.parent == root.path else path.parent.name
        return _Target(path, f"{here}, en {parent}", tuple(guessed))

    def _search(
        self, steps: Sequence[str], roots: Sequence[Root], scope: Scope, also: Root | None = None
    ) -> _Target:
        """Busca la primera subcarpeta en todas las carpetas permitidas, de la forma más estricta
        a la más suelta: una coincidencia estricta en un lugar le gana a una suelta en otro."""
        searched = [root for root in roots if root.searched]
        if not searched:
            raise ToolError(_NO_ACCESS.format(where="ninguna carpeta"))
        for search in SEARCHES:
            # La misma carpeta puede estar a la vista desde dos lugares permitidos.
            hits: dict[str, Root] = {}
            for root in searched:
                if hit := search(steps[0], root.path, scope):
                    hits.setdefault(path_key(hit), root)
            if len(hits) > 1:
                places = _join(list(dict.fromkeys(root.name for root in hits.values())))
                raise ToolError(
                    f"Hay una carpeta «{steps[0]}» en varios lugares: {places}. "
                    "Preguntale al usuario cuál quiere."
                )
            if hits:
                return self._descend(next(iter(hits.values())), steps, scope)
        bases = [*searched, *([also] if also and also not in searched else [])]
        raise _NotFound(
            0,
            steps[0],
            _join([root.name for root in searched]),
            len(steps) == 1,
            self._candidates(steps[0], [root.path for root in bases], scope, roots),
        )

    def _candidates(
        self, name: str, bases: Sequence[Path], scope: Scope, roots: Sequence[Root]
    ) -> Callable[[], list[_Candidate]]:
        """Las carpetas que podrían ser la pedida, cada una con dónde está."""
        names = {path_key(root.path): root.name for root in roots}

        def found() -> list[_Candidate]:
            return [
                (path, names.get(path_key(path.parent), path.parent.name))
                for path in closest(name, bases, scope)
            ]

        return found
