import logging
logger = logging.getLogger(__name__)

import os
import traceback
from concurrent.futures import ThreadPoolExecutor
from time import sleep
from datetime import datetime

from netcore import GenericHandler, AutoParseTextFSM
from PyQt5 import QtCore


class OpenSession(QtCore.QThread):
    """
    Manages an interactive PTY session in a background thread.
    Emits results or failures using PyQt signals.
    """
    return_text = QtCore.pyqtSignal(dict)
    session_failed = QtCore.pyqtSignal(dict)

    def __init__(self, **kwargs):
        """
        Initializes the session with connection arguments.
        """
        super().__init__()
        self.kwargs = kwargs
        self.name = kwargs.get('hostname')
        self.pty = None
        self.prompt = ''
        self._commands = []
        self._lock = QtCore.QMutex()
        self._running = True
        logger.debug(f"OpenSession initialized for {self.name}")

    def run(self):
        """
        Starts the PTY session and handles command execution.
        """
        try:
            logger.info(f"Connecting to {self.name}")
            self.pty = GenericHandler(**self.kwargs)
            output = self.pty.clear_buffer()
            self.prompt = f"{self.pty.find_prompt()} "
            self.return_text.emit({'prompt': self.prompt, 'output': output})
            logger.info(f"Connected to {self.name}")
        except Exception:
            logger.error(f"Connection failed to {self.name}")
            self.session_failed.emit({'prompt': '', 'output': traceback.format_exc()})
            return

        while self._running:
            self._lock.lock()
            try:
                if self._commands:
                    cmd = self._commands.pop(0)
                    logger.debug(f"Executing command: {cmd}")
                    try:
                        output = self.pty.send_command(cmd)
                        try:
                            parsed = AutoParseTextFSM(output, cmd, self.pty.device_type).parse()
                        except Exception as error:
                            logger.warning(f"Parsing failed for command '{cmd}': {error}")
                            parsed = str(error)

                        self.return_text.emit({
                            'prompt': self.prompt,
                            'output': f"{cmd}\n{output}\n",
                            'parsed': parsed
                        })
                    except Exception:
                        logger.error(f"Command execution failed: {cmd}")
                        self.return_text.emit({
                            'prompt': '',
                            'output': f"[Command Error]\n{traceback.format_exc()}\n"
                        })
            finally:
                self._lock.unlock()
            self.msleep(100)

    def execute_command(self, cmd):
        """
        Queues a command for execution.
        """
        logger.debug(f"Command queued: {cmd}")
        self._lock.lock()
        self._commands.append(cmd)
        self._lock.unlock()

        if hasattr(logger, 'savings'):
            logger.savings(10)

    def stop(self):
        """
        Gracefully stops the session thread.
        """
        logger.info(f"Stopping session thread for {self.name}")
        self._running = False
        self.wait()

    def close(self):
        """
        Disconnects the session and releases resources.
        """
        try:
            logger.info(f"Closing connection to {self.name}")
            self.pty.disconnect()
        except Exception:
            logger.error(f"Closure failed for {self.name}")
            self.return_text.emit({
                'prompt': '',
                'output': f"[Command Error]\n{traceback.format_exc()}\n"
            })
