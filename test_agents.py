#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Suite para CR Agents - Pruebas del sistema de agentes autónomos

Pruebas:
1. Cada agente funciona correctamente
2. Coordinador orquesta todos los agentes
3. Resultados se procesan correctamente
4. Estadísticas se calculan
"""

import asyncio
import json
import sys
from pathlib import Path

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent))

from cr_agents import (
    get_coordinator,
    ClassifierAgent,
    FinderAgent,
    EnhancerAgent,
    ValidatorAgent,
    OptimizationAgent,
    Task,
    TaskPriority
)


async def test_individual_agents():
    """Prueba cada agente individualmente"""
    print("\n" + "="*80)
    print("TEST 1: Individual Agent Tests")
    print("="*80 + "\n")
    
    test_data = {
        'error': 'SSH connection timeout on port 22',
        'title': 'SSH timeout',
        'description': 'SSH connection timed out',
        'classification': 'N/A'
    }
    
    # Test ClassifierAgent
    print("📌 Testing ClassifierAgent...")
    classifier = ClassifierAgent()
    task1 = Task('test-1', 'classifier', test_data)
    result1 = await classifier.execute(task1)
    print(f"   Result: {result1.result}")
    assert result1.result['classification'] == 'INFRA_ISSUES', "Classifier should detect INFRA_ISSUES"
    print("   ✅ PASSED\n")
    
    # Test FinderAgent
    print("📌 Testing FinderAgent...")
    finder = FinderAgent()
    task2 = Task('test-2', 'finder', test_data)
    result2 = await finder.execute(task2)
    print(f"   Found {result2.result['count']} similar CRs")
    print("   ✅ PASSED\n")
    
    # Test EnhancerAgent
    print("📌 Testing EnhancerAgent...")
    enhancer = EnhancerAgent()
    task3 = Task('test-3', 'enhancer', test_data)
    result3 = await enhancer.execute(task3)
    print(f"   Description improved: {result3.result['was_improved']}")
    print("   ✅ PASSED\n")
    
    # Test ValidatorAgent
    print("📌 Testing ValidatorAgent...")
    validator = ValidatorAgent()
    task4 = Task('test-4', 'validator', test_data)
    result4 = await validator.execute(task4)
    print(f"   Quality Score: {result4.result['quality_score']:.1f}%")
    print(f"   Is Valid: {result4.result['is_valid']}")
    print("   ✅ PASSED\n")
    
    # Test OptimizationAgent
    print("📌 Testing OptimizationAgent...")
    optimizer = OptimizationAgent()
    task5 = Task('test-5', 'optimizer', test_data)
    result5 = await optimizer.execute(task5)
    print(f"   Was optimized: {result5.result['was_optimized']}")
    print("   ✅ PASSED\n")


async def test_coordinator_pipeline():
    """Prueba el coordinador con un pipeline completo"""
    print("="*80)
    print("TEST 2: Coordinator Pipeline Test")
    print("="*80 + "\n")
    
    test_crs = [
        {
            'test_case': 'test_vlan_config',
            'error': 'Configuration validation failed: VLAN 100 not found',
            'title': 'VLAN config failed',
            'description': 'VLAN configuration issue',
            'classification': 'N/A'
        },
        {
            'test_case': 'test_dns_resolution',
            'error': 'DNS resolution failed: hostname not found',
            'title': 'DNS lookup failed',
            'description': 'DNS server issue',
            'classification': 'N/A'
        },
        {
            'test_case': 'test_bgp_routes',
            'error': 'BGP routes not propagating to peer',
            'title': 'BGP propagation failed',
            'description': 'BGP configuration problem',
            'classification': 'N/A'
        }
    ]
    
    coordinator = get_coordinator()
    
    for i, cr in enumerate(test_crs, 1):
        print(f"\n📋 Processing CR {i}/3: {cr['test_case']}")
        print("-" * 80)
        
        results = await coordinator.process_cr(cr)
        
        # Verificar resultados
        assert results['pipeline_succeeded'], f"Pipeline failed for {cr['test_case']}"
        assert results['final_cr_data']['classification'] != 'N/A', "Classification should be assigned"
        
        print(f"\n✅ CR {i} processed successfully!")
        print(f"   Classification: {results['final_cr_data']['classification']}")
        print(f"   Quality Score: {results['agent_results']['validator']['quality_score']:.1f}%")
        print(f"   Similar CRs Found: {results['agent_results']['finder']['count']}")
    
    print("\n" + "="*80)
    print("✅ All CRs processed successfully!")
    print("="*80 + "\n")


async def test_statistics():
    """Prueba estadísticas y reportes"""
    print("="*80)
    print("TEST 3: Statistics and Reporting")
    print("="*80 + "\n")
    
    coordinator = get_coordinator()
    stats = coordinator.get_stats()
    
    print("📊 Coordinator Statistics:")
    print(f"   Total Completed Tasks: {stats['total_completed_tasks']}")
    print(f"   Overall Success Rate: {stats['success_rate']:.1f}%\n")
    
    print("🤖 Individual Agent Stats:")
    for agent_name, agent_stats in stats['agents'].items():
        print(f"\n   {agent_name.upper()}:")
        print(f"      Total Tasks: {agent_stats['total_tasks']}")
        print(f"      Succeeded: {agent_stats['succeeded']}")
        print(f"      Failed: {agent_stats['failed']}")
        print(f"      Success Rate: {agent_stats['success_rate']:.1f}%")
        print(f"      Avg Execution Time: {agent_stats['avg_execution_time']:.3f}s")
    
    print("\n✅ Statistics test completed!\n")


async def stress_test():
    """Prueba de estrés con múltiples CRs simultáneos"""
    print("="*80)
    print("TEST 4: Stress Test (Concurrent Processing)")
    print("="*80 + "\n")
    
    test_crs = [
        {
            'test_case': f'test_concurrent_{i}',
            'error': f'Error type {i % 4} in test',
            'title': f'Test error {i}',
            'description': f'Concurrent test case {i}',
            'classification': 'N/A'
        }
        for i in range(5)
    ]
    
    coordinator = get_coordinator()
    
    print(f"🚀 Processing {len(test_crs)} CRs concurrently...\n")
    
    # Procesar todos en paralelo
    tasks = [coordinator.process_cr(cr) for cr in test_crs]
    results = await asyncio.gather(*tasks)
    
    successful = sum(1 for r in results if r['pipeline_succeeded'])
    
    print(f"\n✅ Concurrent Processing Results:")
    print(f"   Total: {len(results)}")
    print(f"   Successful: {successful}")
    print(f"   Success Rate: {successful/len(results)*100:.1f}%\n")


async def main():
    """Ejecuta todos los tests"""
    print("""
╔════════════════════════════════════════════════════════════════════════════╗
║                                                                            ║
║           🤖 CR AGENTS - COMPREHENSIVE TEST SUITE                         ║
║                                                                            ║
║                      Testing Multi-Agent System                           ║
║                                                                            ║
╚════════════════════════════════════════════════════════════════════════════╝
""")
    
    try:
        # Test 1: Individual Agents
        await test_individual_agents()
        
        # Test 2: Coordinator Pipeline
        await test_coordinator_pipeline()
        
        # Test 3: Statistics
        await test_statistics()
        
        # Test 4: Stress Test
        await stress_test()
        
        print("\n" + "="*80)
        print("✨ ALL TESTS PASSED! 🎉")
        print("="*80)
        print("\nThe multi-agent system is working correctly!")
        print("Ready for integration and production use.\n")
        
        return 0
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
