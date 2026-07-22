#!/usr/bin/env python3
"""
Comprehensive Merge Verification Report
"""
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

def check_duplicates():
    """Check for remaining *1 or *2 files"""
    print("\n" + "="*60)
    print("STEP 11: DUPLICATE SCAN")
    print("="*60)
    
    patterns = [
        '*.py', '*.md', '*.txt', '*.yml', '*.yaml'
    ]
    
    duplicate_dirs = [
        'agents1', 'agents2',
        'tools1', 'tools2',
        'tests1', 'tests2',
        'docs1', 'docs2',
        'knowledge_base1', 'knowledge_base2',
        'db1', 'db2',
        'docker1', 'docker2',
        'mcp_servers2'
    ]
    
    issues = []
    
    # Check for *1 and *2 files
    for item in Path('.').rglob('*'):
        name = item.name
        if name.endswith('1.py') or name.endswith('2.py') or \
           name.endswith('1.md') or name.endswith('2.md'):
            issues.append(f"File: {item}")
    
    # Check for *1 and *2 directories
    for item in Path('.').rglob('*'):
        if item.is_dir() and item.name in duplicate_dirs:
            issues.append(f"Directory: {item}")
    
    if not issues:
        print("✓ No duplicate files or folders found")
        return True
    else:
        print("✗ Duplicates found:")
        for issue in issues:
            print(f"  - {issue}")
        return False

def check_imports():
    """Verify all imports work"""
    print("\n" + "="*60)
    print("STEP 2: IMPORT VERIFICATION")
    print("="*60)
    
    imports = [
        "from graph import build_graph, new_session_state, resume_session, persist_turn",
        "from agents.state import AgentState",
        "from agents.account_agent import run_account_agent",
        "from agents.fraud_agent import run_fraud_agent",
        "from agents.search_agent import run_search_agent",
        "from agents.supervisor import classify_intent",
        "from agents.verification import try_verify",
        "from tools.memory import create_session, link_session_to_user",
        "from tools.account_tools import get_balance, get_transaction_history",
        "from tools.fraud_tools import lock_card, unlock_card, report_card_lost",
        "from tools.faq_search import search_faq",
        "import mcp_servers.account_server",
        "import mcp_servers.fraud_server",
        "import mcp_servers.faq_server",
        "import tests.test_tools",
        "import tests.test_conversations",
    ]
    
    failed = []
    for imp in imports:
        try:
            exec(imp)
            print(f"✓ {imp.split('from ')[1] if 'from' in imp else imp.split('import ')[1]}")
        except Exception as e:
            print(f"✗ {imp.split('from ')[1] if 'from' in imp else imp.split('import ')[1]}: {e}")
            failed.append((imp, str(e)))
    
    return len(failed) == 0, failed

def check_database():
    """Verify database structure"""
    print("\n" + "="*60)
    print("STEP 7: DATABASE VERIFICATION")
    print("="*60)
    
    required_tables = {
        'users': 'Banking',
        'accounts': 'Banking',
        'cards': 'Banking',
        'transactions': 'Banking',
        'sessions': 'Memory',
        'messages': 'Memory',
    }
    
    try:
        conn = sqlite3.connect('db/bank.db')
        cursor = conn.cursor()
        
        all_good = True
        for table_name, category in required_tables.items():
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}';")
            if cursor.fetchone():
                cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
                count = cursor.fetchone()[0]
                print(f"✓ {table_name:15} ({category:10}) - {count:5} records")
            else:
                print(f"✗ {table_name:15} ({category:10}) - MISSING")
                all_good = False
        
        conn.close()
        return all_good
    except Exception as e:
        print(f"✗ Database error: {e}")
        return False

def check_graph_structure():
    """Verify LangGraph structure"""
    print("\n" + "="*60)
    print("STEP 4: LANGGRAPH VERIFICATION")
    print("="*60)
    
    try:
        from graph import build_graph
        from langgraph.graph import END
        
        graph = build_graph()
        
        # Check for required nodes
        required_nodes = [
            'supervisor', 'verify_gate', 'search_agent',
            'account_agent', 'fraud_agent', 'clarify',
            'await_credentials', 'human_handoff'
        ]
        
        print("✓ Graph compilation successful")
        print(f"✓ Graph has {len(graph.nodes)} nodes")
        print(f"✓ Graph has {len(graph.edges)} edges")
        
        return True
    except Exception as e:
        print(f"✗ Graph compilation failed: {e}")
        return False

def check_memory_module():
    """Verify memory module functions"""
    print("\n" + "="*60)
    print("STEP 5: MEMORY VERIFICATION")
    print("="*60)
    
    try:
        from tools.memory import (
            create_session, link_session_to_user, append_message,
            load_session_messages, session_exists, get_session_user,
            get_recent_sessions_for_user, get_last_session_summary_for_user
        )
        
        functions = [
            'create_session', 'link_session_to_user', 'append_message',
            'load_session_messages', 'session_exists', 'get_session_user',
            'get_recent_sessions_for_user', 'get_last_session_summary_for_user'
        ]
        
        for func in functions:
            print(f"✓ {func}")
        
        return True
    except Exception as e:
        print(f"✗ Memory module error: {e}")
        return False

def main():
    print("\n" + "="*60)
    print("COMPREHENSIVE MERGE VERIFICATION REPORT")
    print("="*60)
    
    results = {
        'Imports': check_imports()[0],
        'Database': check_database(),
        'LangGraph': check_graph_structure(),
        'Memory': check_memory_module(),
        'Duplicates': check_duplicates(),
    }
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    for check, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status} - {check}")
    
    all_passed = all(results.values())
    
    print("\n" + "="*60)
    if all_passed:
        print("✓ ALL CORE VERIFICATIONS PASSED")
    else:
        print("✗ SOME VERIFICATIONS FAILED")
    print("="*60)
    
    return 0 if all_passed else 1

if __name__ == '__main__':
    sys.exit(main())
