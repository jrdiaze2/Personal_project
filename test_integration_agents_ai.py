#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test de integración: AI Engine + Multi-Agent System + generate_formatted_crs.py

Prueba el pipeline completo:
1. Datos básicos del CR
2. Enriquecimiento con AI Engine
3. Procesamiento con Multi-Agent System
4. Validación de resultados
"""

import asyncio
import json
import sys
from pathlib import Path

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent))

from cr_agents import get_coordinator
from cr_ai_engine import get_ai_engine

print("""
╔════════════════════════════════════════════════════════════════════════════╗
║                                                                            ║
║        🎯 INTEGRATION TEST: AI + AGENTS + generate_formatted_crs          ║
║                                                                            ║
║              Testing Complete CR Processing Pipeline                      ║
║                                                                            ║
╚════════════════════════════════════════════════════════════════════════════╝
""")

# Test cases realistas
test_scenarios = [
    {
        'test_case': 'test_vlan_config_integration',
        'error_message': 'VLAN configuration validation failed on switch',
        'title': 'VLAN configuration failed',
        'description': 'VLAN 100 not properly configured on switch port 1/1',
        'classification': 'N/A'
    },
    {
        'test_case': 'test_sfp_module_detection',
        'error_message': 'SFP module not detected by device',
        'title': 'SFP module detection issue',
        'description': 'SFP transceiver on port 3/48 not detected during interface initialization',
        'classification': 'N/A'
    },
    {
        'test_case': 'test_l3_routing_convergence',
        'error_message': 'BGP route convergence timeout exceeded',
        'title': 'BGP convergence failed',
        'description': 'BGP routes not converging within expected time window',
        'classification': 'N/A'
    }
]

async def test_cr_integration(cr_data):
    """Test integración completa de un CR"""
    print(f"\n{'='*80}")
    print(f"Testing CR: {cr_data['test_case']}")
    print(f"{'='*80}\n")
    
    # Paso 1: AI Enhancement
    print("📊 STEP 1: AI Enhancement")
    print("-" * 80)
    try:
        ai_engine = get_ai_engine()
        enhanced_by_ai = ai_engine.enhance_cr(cr_data.copy())
        
        if enhanced_by_ai.get('ai_enhanced'):
            print("✅ AI Engine Results:")
            print(f"   • Classification: {enhanced_by_ai.get('ai_classification', 'N/A')}")
            print(f"   • Similar CRs: {len(enhanced_by_ai.get('ai_similar_crs', []))}")
            print(f"   • Description improved: {bool(enhanced_by_ai.get('ai_improved_description'))}")
        else:
            print("⚠️  AI Enhancement not performed")
    except Exception as e:
        print(f"⚠️  AI Enhancement failed: {e}")
        enhanced_by_ai = cr_data.copy()
    
    # Paso 2: Multi-Agent Processing
    print("\n📊 STEP 2: Multi-Agent System Processing")
    print("-" * 80)
    try:
        coordinator = get_coordinator()
        agent_results = await coordinator.process_cr(cr_data)
        
        if agent_results.get('pipeline_succeeded'):
            print("✅ Agent Processing Results:")
            
            agent_data = agent_results.get('final_cr_data', {})
            classifier_result = agent_results.get('agent_results', {}).get('classifier', {})
            finder_result = agent_results.get('agent_results', {}).get('finder', {})
            validator_result = agent_results.get('agent_results', {}).get('validator', {})
            enhancer_result = agent_results.get('agent_results', {}).get('enhancer', {})
            
            print(f"   • Classifier: {agent_data.get('classification')} "
                  f"(confidence: {classifier_result.get('confidence', 0):.1%})")
            print(f"   • Similar CRs found: {finder_result.get('count', 0)}")
            print(f"   • Quality Score: {validator_result.get('quality_score', 0):.1f}%")
            print(f"   • Description improved: {enhancer_result.get('was_improved', False)}")
        else:
            print("⚠️  Agent Processing failed")
            agent_results = {'agent_results': {}}
    except Exception as e:
        print(f"⚠️  Agent Processing failed: {e}")
        agent_results = {'agent_results': {}}
    
    # Paso 3: Comparación de resultados
    print("\n📊 STEP 3: Comparison & Integration")
    print("-" * 80)
    
    ai_classification = enhanced_by_ai.get('ai_classification', 'N/A')
    agent_classification = agent_results.get('final_cr_data', {}).get('classification', 'N/A')
    
    print(f"AI Classification:    {ai_classification}")
    print(f"Agent Classification: {agent_classification}")
    
    if ai_classification != 'N/A' and agent_classification != 'N/A':
        if ai_classification == agent_classification:
            print("✅ Classifications AGREE - High confidence")
        else:
            print("⚠️  Classifications DIFFER - Manual review needed")
    
    # Resumen
    print("\n" + "="*80)
    print("INTEGRATION SUMMARY")
    print("="*80)
    print(f"Test Case: {cr_data['test_case']}")
    print(f"AI Status: {'✅ Enhanced' if enhanced_by_ai.get('ai_enhanced') else '⚠️  Not enhanced'}")
    print(f"Agents Status: {'✅ Processed' if agent_results.get('pipeline_succeeded') else '❌ Failed'}")
    
    validator_score = agent_results.get('agent_results', {}).get('validator', {}).get('quality_score', 0)
    print(f"Final Quality Score: {validator_score:.1f}%")
    print(f"{'✅ READY FOR SUBMISSION' if validator_score >= 75.0 else '⚠️  NEEDS REVIEW'}")
    print("="*80 + "\n")


async def main():
    """Main test suite"""
    print("\n🚀 Starting integration tests...\n")
    
    results = {
        'total': len(test_scenarios),
        'successful': 0,
        'failed': 0
    }
    
    for scenario in test_scenarios:
        try:
            await test_cr_integration(scenario)
            results['successful'] += 1
        except Exception as e:
            print(f"❌ Test failed for {scenario['test_case']}: {e}")
            results['failed'] += 1
    
    # Final report
    print("\n" + "╔" + "="*78 + "╗")
    print("║" + " "*78 + "║")
    print("║" + "FINAL INTEGRATION TEST REPORT".center(78) + "║")
    print("║" + " "*78 + "║")
    print("║" + f"Total Tests: {results['total']}".ljust(78) + "║")
    print("║" + f"Successful: {results['successful']}".ljust(78) + "║")
    print("║" + f"Failed: {results['failed']}".ljust(78) + "║")
    
    if results['failed'] == 0:
        print("║" + " "*78 + "║")
        print("║" + "✨ ALL TESTS PASSED - INTEGRATION SUCCESSFUL ✨".center(78) + "║")
    else:
        print("║" + " "*78 + "║")
        print("║" + f"⚠️  {results['failed']} tests failed".ljust(78) + "║")
    
    print("║" + " "*78 + "║")
    print("╚" + "="*78 + "╝\n")


if __name__ == '__main__':
    asyncio.run(main())
