"""The default pet must start Electron for the serving port, never a VTS capture process."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import pet_control as pet


class WebPetTests(unittest.TestCase):
    def test_boolean_required(self):
        for value in (1, 'true', None):
            with self.assertRaises(ValueError):
                pet.switch(value)

    def test_status_requires_electron_not_vts(self):
        with patch.object(pet, '_window', return_value=None), patch.object(pet, 'executable', return_value='electron.exe') as exe:
            result=pet.status(61945)
        exe.assert_called_once_with('electron')
        self.assertFalse(result['requiresVts'])
        self.assertEqual(result['sourceUrl'], 'http://127.0.0.1:61945/pet.html')
        self.assertFalse(result['running'])

    def test_launch_uses_actual_port_and_removes_run_as_node(self):
        with tempfile.TemporaryDirectory() as folder:
            proc=MagicMock();proc.poll.return_value=None
            env=SimpleNamespace(name='nt',environ={'ELECTRON_RUN_AS_NODE':'1','PATH':'keep'})
            with patch.object(pet,'ROOT',Path(folder)), patch.object(pet,'os',env), \
                 patch.object(pet,'_window',return_value=None), \
                 patch.object(pet,'executable',return_value='electron.exe'), \
                 patch.object(pet,'status',return_value={'running':True,'ready':True,'renderer':'web'}), \
                 patch.object(pet.subprocess,'CREATE_NO_WINDOW',0,create=True), \
                 patch.object(pet.subprocess,'Popen',return_value=proc) as spawn:
                result=pet.switch(True,61945)
            command=spawn.call_args.args[0]
            self.assertEqual(command,[ 'electron.exe',str(Path(folder)/'desktop-pet'),'--url','http://127.0.0.1:61945'])
            self.assertNotIn('ELECTRON_RUN_AS_NODE',spawn.call_args.kwargs['env'])
            self.assertTrue(result['ready'])

    def test_existing_pet_is_not_duplicated(self):
        with patch.object(pet,'os',SimpleNamespace(name='nt')), \
             patch.object(pet,'_window',return_value=123), \
             patch.object(pet,'status',return_value={'running':True}), \
             patch.object(pet.subprocess,'Popen') as spawn:
            self.assertTrue(pet.switch(True,61944)['running'])
            spawn.assert_not_called()


if __name__=='__main__':
    unittest.main()
