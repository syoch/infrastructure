import os
import sys
import unittest
import asyncio
from datetime import datetime

# Set up paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PORTAL_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
if PORTAL_DIR not in sys.path:
    sys.path.insert(0, PORTAL_DIR)

from backend.core.database import session_scope, Base, get_engine
from servers.control_plane.models import Device, DeviceACL, CommandRequest
from servers.control_plane.core import can_issue, EventBus, get_current_device

class TestControlPlaneCore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Ensure we use in-memory for testing
        os.environ["PORTAL_DATABASE_URL"] = "sqlite:///:memory:"
        from backend.core import config
        config.DATABASE_URL = "sqlite:///:memory:"
        Base.metadata.create_all(get_engine())

    def setUp(self):
        # Clear data before each test
        with session_scope() as session:
            session.query(CommandRequest).delete()
            session.query(DeviceACL).delete()
            session.query(Device).delete()
            session.commit()

    def test_acl_matching(self):
        with session_scope() as session:
            # 1. Exact match
            session.add(DeviceACL(source_device="device:src1", target_device="device:tgt1", operation="echo"))
            # 2. Regex source
            session.add(DeviceACL(source_device="device:web-.*", target_device="device:agent1", operation=".*"))
            # 3. Regex operation
            session.add(DeviceACL(source_device="device:src2", target_device="device:tgt2", operation=r"^sys\..*"))
            session.commit()

            # Exact match
            self.assertTrue(can_issue(session, "src1", "tgt1", "echo"))
            self.assertFalse(can_issue(session, "src1", "tgt1", "other"))

            # Regex source
            self.assertTrue(can_issue(session, "web-admin", "agent1", "reboot"))
            self.assertTrue(can_issue(session, "web-ui-123", "agent1", "anything"))
            self.assertFalse(can_issue(session, "mobile-app", "agent1", "reboot"))

            # Regex operation
            self.assertTrue(can_issue(session, "src2", "tgt2", "sys.reboot"))
            self.assertTrue(can_issue(session, "src2", "tgt2", "sys.update"))
            self.assertFalse(can_issue(session, "src2", "tgt2", "echo"))

    def test_event_bus(self):
        bus = EventBus()
        loop = asyncio.new_event_loop()

        async def run_bus_test():
            q = await bus.subscribe()
            
            # Publish event
            ev = {"type": "test", "command_id": "c1", "status": "ok"}
            await bus.publish(ev)
            
            # Receive event
            received = await asyncio.wait_for(q.get(), timeout=1.0)
            self.assertEqual(received["command_id"], "c1")
            
            # Snapshots: new subscriber gets last status
            q2 = await bus.subscribe()
            snap = await asyncio.wait_for(q2.get(), timeout=1.0)
            self.assertEqual(snap["command_id"], "c1")
            
            await bus.unsubscribe(q)
            await bus.unsubscribe(q2)

        loop.run_until_complete(run_bus_test())
        loop.close()

    def test_auth_resolver(self):
        from fastapi import HTTPException
        
        with session_scope() as session:
            d = Device(id="d1", display_name="D1", bearer_token="tk_123")
            session.add(d)
            session.commit()

            # Valid token
            resolved = get_current_device(authorization="Bearer tk_123", token="", db=session)
            self.assertEqual(resolved.id, "d1")

            # Query token
            resolved = get_current_device(authorization="", token="tk_123", db=session)
            self.assertEqual(resolved.id, "d1")

            # Invalid
            with self.assertRaises(HTTPException) as cm:
                get_current_device(authorization="Bearer wrong", token="", db=session)
            self.assertEqual(cm.exception.status_code, 401)

if __name__ == "__main__":
    unittest.main()
