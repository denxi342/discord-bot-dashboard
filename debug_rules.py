import sys
import traceback

try:
    with open('debug_output.txt', 'w', encoding='utf-8') as f:
        try:
            from arizona_rules import search_rules, ARIZONA_RULES
            f.write("Successfully imported arizona_rules\n")
            
            query = "что будет за дм"
            f.write(f"Query: {query}\n")
            
            result = search_rules(query)
            
            if result:
                f.write("MATCH FOUND!\n")
                f.write(result[:100] + "...\n")
            else:
                f.write("NO MATCH FOUND.\n")
                
            # Manual Check
            query_lower = query.lower().strip()
            words = query_lower.split()
            f.write(f"Words: {words}\n")
            
            for key, rule in ARIZONA_RULES.items():
                if key == 'dm':
                    f.write(f"Checking key: {key}\n")
                    f.write(f"Keywords: {rule['keywords']}\n")
                    score = 0
                    if key in query_lower:
                         f.write("Direct key match (+100)\n")
                         score += 100
                    
                    for word in words:
                        for keyword in rule['keywords']:
                            # Simple equality check
                            if word == keyword:
                                f.write(f"Keyword EXACT match '{word}' == '{keyword}' (+50)\n")
                                score += 50
                            elif word in keyword:
                                f.write(f"Keyword PARTIAL match '{word}' in '{keyword}' (+30)\n")
                                score += 30
                    
                    f.write(f"Total Score: {score}\n")
                    
        except Exception as e:
            f.write(f"Error: {e}\n")
            traceback.print_exc(file=f)

except Exception as e:
    print(f"Outer Error: {e}")
