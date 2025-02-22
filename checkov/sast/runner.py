from __future__ import annotations

import logging
import os
import pathlib
import sys

from checkov.common.bridgecrew.check_type import CheckType
from checkov.common.output.report import Report
from checkov.common.runners.base_runner import BaseRunner
from checkov.runner_filter import RunnerFilter
from checkov.sast.checks_infra.base_registry import Registry
from checkov.sast.consts import SUPPORT_FILE_EXT, FILE_EXT_TO_SAST_LANG, SastEngines
from checkov.sast.engines.base_engine import SastEngine
from checkov.sast.engines.prisma_engine import PrismaEngine
from checkov.sast.engines.semgrep_engine import SemgrepEngine
from checkov.common.bridgecrew.platform_integration import bc_integration

from typing import List, Optional

logger = logging.getLogger(__name__)

CHECKS_DIR = (os.path.join(pathlib.Path(__file__).parent.resolve(), 'checks'))


class Runner(BaseRunner[None]):
    check_type = CheckType.SAST  # noqa: CCE003  # a static attribute

    def __init__(self) -> None:
        super().__init__(file_extensions=["." + a for a in FILE_EXT_TO_SAST_LANG.keys()])
        self.registry = Registry(checks_dir=CHECKS_DIR)

    def should_scan_file(self, file: str) -> bool:
        for extensions in SUPPORT_FILE_EXT.values():
            for extension in extensions:
                if file.endswith(extension):
                    return True
        return False

    def run(self, root_folder: Optional[str],
            external_checks_dir: Optional[List[str]] = None,
            files: Optional[List[str]] = None,
            runner_filter: Optional[RunnerFilter] = None,
            collect_skip_comments: bool = True) -> List[Report]:

        if sys.platform.startswith('win'):
            # TODO: Enable SAST for windows runners
            return [Report(self.check_type)]

        if not runner_filter:
            logger.warning('no runner filter')
            return [Report(self.check_type)]

        # registry get all the paths
        self.registry.set_runner_filter(runner_filter)
        self.registry.add_external_dirs(external_checks_dir)

        targets = []
        if root_folder:
            if not os.path.isabs(root_folder):
                root_folder = os.path.abspath(root_folder)
            targets.append(root_folder)
        if files:
            targets.extend([a if os.path.isabs(a) else os.path.abspath(a) for a in files])

        engine_name = self.get_engine()
        engine: SastEngine
        if engine_name == SastEngines.SEMGREP:
            engine = SemgrepEngine()  # noqa: disallow-untyped-calls
        elif engine_name == SastEngines.PRISMA:
            engine = PrismaEngine()  # noqa: disallow-untyped-calls
        else:
            logging.error(f"not supported engine: {engine_name}")
            return [Report(self.check_type)]

        reports = []
        try:
            reports = engine.get_reports(targets, self.registry, runner_filter.sast_languages)
        except BaseException as e:
            logger.error(f"got error when try to run prisma sast, fallback to semgrep: {e}")
            if engine_name == SastEngines.PRISMA:
                engine = SemgrepEngine()  # noqa: disallow-untyped-calls
                reports = engine.get_reports(targets, self.registry, runner_filter.sast_languages)

        return reports

    @staticmethod
    def get_engine() -> SastEngines:
        if bc_integration.bc_api_key and not os.getenv("IS_TEST"):
            return SastEngines.PRISMA
        return SastEngines.SEMGREP
