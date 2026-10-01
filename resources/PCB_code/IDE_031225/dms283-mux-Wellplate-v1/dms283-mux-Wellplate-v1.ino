/* 
Projet Wellplate DMS283
Version 1.0 25.11.2025
DMS Hepia HES-SO FMo
Arduino DUE
*/

# define SW_BP1 22
# define SW_BP2 24
# define MUX1_1_EN 26
# define MUX2_1_EN 28
# define MUX1_2_EN 30
# define MUX2_2_EN 32
# define MUX1_1_A0 23
# define MUX1_1_A1 25
# define MUX1_1_A2 27
# define MUX1_1_A3 29
# define MUX1_2_A0 31
# define MUX1_2_A1 33
# define MUX1_2_A2 35
# define MUX2_1_A0 37
# define MUX2_1_A1 39
# define MUX2_1_A2 41
# define MUX2_1_A3 43
# define MUX2_2_A0 45
# define MUX2_2_A1 47
# define MUX2_2_A2 49

void BP1(int BP) {
  //bypass
  if (BP == 1) {
    digitalWrite(SW_BP1, LOW);
    }
  else if (BP == 0){
    digitalWrite(SW_BP1, HIGH);
    }
}

void BP2(int BP) {
  //bypass
  if (BP == 1) {
    digitalWrite(SW_BP2, LOW);
    }
  else if (BP == 0){
    digitalWrite(SW_BP2, HIGH);
    }
}

void IN1(String WELL) {
   //selection puit
  if (WELL == "A1") {
    digitalWrite(MUX1_1_EN, HIGH);
    digitalWrite(MUX1_1_A0, LOW); 
    digitalWrite(MUX1_1_A1, LOW); 
    digitalWrite(MUX1_1_A2, LOW); 
    digitalWrite(MUX1_1_A3, LOW);
    digitalWrite(MUX1_2_EN, LOW); 
    digitalWrite(MUX1_2_A0, LOW); 
    digitalWrite(MUX1_2_A1, LOW); 
    digitalWrite(MUX1_2_A2, LOW);
  }
  else if (WELL == "A2") {
    digitalWrite(MUX1_1_EN, HIGH);
    digitalWrite(MUX1_1_A0, LOW); 
    digitalWrite(MUX1_1_A1, LOW); 
    digitalWrite(MUX1_1_A2, HIGH); 
    digitalWrite(MUX1_1_A3, LOW);
    digitalWrite(MUX1_2_EN, LOW); 
    digitalWrite(MUX1_2_A0, LOW); 
    digitalWrite(MUX1_2_A1, LOW); 
    digitalWrite(MUX1_2_A2, LOW);
  }
  else if (WELL == "A3") {
    digitalWrite(MUX1_1_EN, HIGH);
    digitalWrite(MUX1_1_A0, LOW); 
    digitalWrite(MUX1_1_A1, LOW); 
    digitalWrite(MUX1_1_A2, LOW); 
    digitalWrite(MUX1_1_A3, HIGH);
    digitalWrite(MUX1_2_EN, LOW); 
    digitalWrite(MUX1_2_A0, LOW); 
    digitalWrite(MUX1_2_A1, LOW); 
    digitalWrite(MUX1_2_A2, LOW);
  }
  else if (WELL == "A4") {
    digitalWrite(MUX1_1_EN, HIGH);
    digitalWrite(MUX1_1_A0, LOW); 
    digitalWrite(MUX1_1_A1, LOW); 
    digitalWrite(MUX1_1_A2, HIGH); 
    digitalWrite(MUX1_1_A3, HIGH);
    digitalWrite(MUX1_2_EN, LOW); 
    digitalWrite(MUX1_2_A0, LOW); 
    digitalWrite(MUX1_2_A1, LOW); 
    digitalWrite(MUX1_2_A2, LOW);
  }
  else if (WELL == "A5") {
    digitalWrite(MUX1_1_EN, LOW);
    digitalWrite(MUX1_1_A0, LOW); 
    digitalWrite(MUX1_1_A1, LOW); 
    digitalWrite(MUX1_1_A2, LOW); 
    digitalWrite(MUX1_1_A3, LOW);
    digitalWrite(MUX1_2_EN, HIGH); 
    digitalWrite(MUX1_2_A0, LOW); 
    digitalWrite(MUX1_2_A1, LOW); 
    digitalWrite(MUX1_2_A2, LOW);
  }
  else if (WELL == "A6") {
    digitalWrite(MUX1_1_EN, LOW);
    digitalWrite(MUX1_1_A0, LOW); 
    digitalWrite(MUX1_1_A1, LOW); 
    digitalWrite(MUX1_1_A2, LOW); 
    digitalWrite(MUX1_1_A3, LOW);
    digitalWrite(MUX1_2_EN, HIGH); 
    digitalWrite(MUX1_2_A0, LOW); 
    digitalWrite(MUX1_2_A1, LOW); 
    digitalWrite(MUX1_2_A2, HIGH);
  }
  else if (WELL == "B1") {
    digitalWrite(MUX1_1_EN, HIGH);
    digitalWrite(MUX1_1_A0, HIGH); 
    digitalWrite(MUX1_1_A1, LOW); 
    digitalWrite(MUX1_1_A2, LOW); 
    digitalWrite(MUX1_1_A3, LOW);
    digitalWrite(MUX1_2_EN, LOW); 
    digitalWrite(MUX1_2_A0, LOW); 
    digitalWrite(MUX1_2_A1, LOW); 
    digitalWrite(MUX1_2_A2, LOW);
  }
  else if (WELL == "B2") {
    digitalWrite(MUX1_1_EN, HIGH);
    digitalWrite(MUX1_1_A0, HIGH); 
    digitalWrite(MUX1_1_A1, LOW); 
    digitalWrite(MUX1_1_A2, HIGH); 
    digitalWrite(MUX1_1_A3, LOW);
    digitalWrite(MUX1_2_EN, LOW); 
    digitalWrite(MUX1_2_A0, LOW); 
    digitalWrite(MUX1_2_A1, LOW); 
    digitalWrite(MUX1_2_A2, LOW);
  }
  else if (WELL == "B3") {
    digitalWrite(MUX1_1_EN, HIGH);
    digitalWrite(MUX1_1_A0, HIGH); 
    digitalWrite(MUX1_1_A1, LOW); 
    digitalWrite(MUX1_1_A2, LOW); 
    digitalWrite(MUX1_1_A3, HIGH);
    digitalWrite(MUX1_2_EN, LOW); 
    digitalWrite(MUX1_2_A0, LOW); 
    digitalWrite(MUX1_2_A1, LOW); 
    digitalWrite(MUX1_2_A2, LOW);
  }
  else if (WELL == "B4") {
    digitalWrite(MUX1_1_EN, HIGH);
    digitalWrite(MUX1_1_A0, HIGH); 
    digitalWrite(MUX1_1_A1, LOW); 
    digitalWrite(MUX1_1_A2, HIGH); 
    digitalWrite(MUX1_1_A3, HIGH);
    digitalWrite(MUX1_2_EN, LOW); 
    digitalWrite(MUX1_2_A0, LOW); 
    digitalWrite(MUX1_2_A1, LOW); 
    digitalWrite(MUX1_2_A2, LOW);
  }
  else if (WELL == "B5") {
    digitalWrite(MUX1_1_EN, LOW);
    digitalWrite(MUX1_1_A0, LOW); 
    digitalWrite(MUX1_1_A1, LOW); 
    digitalWrite(MUX1_1_A2, LOW); 
    digitalWrite(MUX1_1_A3, LOW);
    digitalWrite(MUX1_2_EN, HIGH); 
    digitalWrite(MUX1_2_A0, HIGH); 
    digitalWrite(MUX1_2_A1, LOW); 
    digitalWrite(MUX1_2_A2, LOW);
  }
  else if (WELL == "B6") {
    digitalWrite(MUX1_1_EN, LOW);
    digitalWrite(MUX1_1_A0, LOW); 
    digitalWrite(MUX1_1_A1, LOW); 
    digitalWrite(MUX1_1_A2, LOW); 
    digitalWrite(MUX1_1_A3, LOW);
    digitalWrite(MUX1_2_EN, HIGH); 
    digitalWrite(MUX1_2_A0, HIGH); 
    digitalWrite(MUX1_2_A1, LOW); 
    digitalWrite(MUX1_2_A2, HIGH);
  }
  else if (WELL == "C1") {
    digitalWrite(MUX1_1_EN, HIGH);
    digitalWrite(MUX1_1_A0, LOW); 
    digitalWrite(MUX1_1_A1, HIGH); 
    digitalWrite(MUX1_1_A2, LOW); 
    digitalWrite(MUX1_1_A3, LOW);
    digitalWrite(MUX1_2_EN, LOW); 
    digitalWrite(MUX1_2_A0, LOW); 
    digitalWrite(MUX1_2_A1, LOW); 
    digitalWrite(MUX1_2_A2, LOW);
  }
  else if (WELL == "C2") {
    digitalWrite(MUX1_1_EN, HIGH);
    digitalWrite(MUX1_1_A0, LOW); 
    digitalWrite(MUX1_1_A1, HIGH); 
    digitalWrite(MUX1_1_A2, HIGH); 
    digitalWrite(MUX1_1_A3, LOW);
    digitalWrite(MUX1_2_EN, LOW); 
    digitalWrite(MUX1_2_A0, LOW); 
    digitalWrite(MUX1_2_A1, LOW); 
    digitalWrite(MUX1_2_A2, LOW);
  }
  else if (WELL == "C3") {
    digitalWrite(MUX1_1_EN, HIGH);
    digitalWrite(MUX1_1_A0, LOW); 
    digitalWrite(MUX1_1_A1, HIGH); 
    digitalWrite(MUX1_1_A2, LOW); 
    digitalWrite(MUX1_1_A3, HIGH);
    digitalWrite(MUX1_2_EN, LOW); 
    digitalWrite(MUX1_2_A0, LOW); 
    digitalWrite(MUX1_2_A1, LOW); 
    digitalWrite(MUX1_2_A2, LOW);
  }
  else if (WELL == "C4") {
    digitalWrite(MUX1_1_EN, HIGH);
    digitalWrite(MUX1_1_A0, LOW); 
    digitalWrite(MUX1_1_A1, HIGH); 
    digitalWrite(MUX1_1_A2, HIGH); 
    digitalWrite(MUX1_1_A3, HIGH);
    digitalWrite(MUX1_2_EN, LOW); 
    digitalWrite(MUX1_2_A0, LOW); 
    digitalWrite(MUX1_2_A1, LOW); 
    digitalWrite(MUX1_2_A2, LOW);
  }
  else if (WELL == "C5") {
    digitalWrite(MUX1_1_EN, LOW);
    digitalWrite(MUX1_1_A0, LOW); 
    digitalWrite(MUX1_1_A1, LOW); 
    digitalWrite(MUX1_1_A2, LOW); 
    digitalWrite(MUX1_1_A3, LOW);
    digitalWrite(MUX1_2_EN, HIGH); 
    digitalWrite(MUX1_2_A0, LOW); 
    digitalWrite(MUX1_2_A1, HIGH); 
    digitalWrite(MUX1_2_A2, LOW);
  }
  else if (WELL == "C6") {
    digitalWrite(MUX1_1_EN, LOW);
    digitalWrite(MUX1_1_A0, LOW); 
    digitalWrite(MUX1_1_A1, LOW); 
    digitalWrite(MUX1_1_A2, LOW); 
    digitalWrite(MUX1_1_A3, LOW);
    digitalWrite(MUX1_2_EN, HIGH); 
    digitalWrite(MUX1_2_A0, LOW); 
    digitalWrite(MUX1_2_A1, HIGH); 
    digitalWrite(MUX1_2_A2, HIGH);
  }
  else if (WELL == "D1") {
    digitalWrite(MUX1_1_EN, HIGH);
    digitalWrite(MUX1_1_A0, HIGH); 
    digitalWrite(MUX1_1_A1, HIGH); 
    digitalWrite(MUX1_1_A2, LOW); 
    digitalWrite(MUX1_1_A3, LOW);
    digitalWrite(MUX1_2_EN, LOW); 
    digitalWrite(MUX1_2_A0, LOW); 
    digitalWrite(MUX1_2_A1, LOW); 
    digitalWrite(MUX1_2_A2, LOW);
  }
  else if (WELL == "D2") {
    digitalWrite(MUX1_1_EN, HIGH);
    digitalWrite(MUX1_1_A0, HIGH); 
    digitalWrite(MUX1_1_A1, HIGH); 
    digitalWrite(MUX1_1_A2, HIGH); 
    digitalWrite(MUX1_1_A3, LOW);
    digitalWrite(MUX1_2_EN, LOW); 
    digitalWrite(MUX1_2_A0, LOW); 
    digitalWrite(MUX1_2_A1, LOW); 
    digitalWrite(MUX1_2_A2, LOW);
  }
  else if (WELL == "D3") {
    digitalWrite(MUX1_1_EN, HIGH);
    digitalWrite(MUX1_1_A0, HIGH); 
    digitalWrite(MUX1_1_A1, HIGH); 
    digitalWrite(MUX1_1_A2, LOW); 
    digitalWrite(MUX1_1_A3, HIGH);
    digitalWrite(MUX1_2_EN, LOW); 
    digitalWrite(MUX1_2_A0, LOW); 
    digitalWrite(MUX1_2_A1, LOW); 
    digitalWrite(MUX1_2_A2, LOW);
  }
  else if (WELL == "D4") {
    digitalWrite(MUX1_1_EN, HIGH);
    digitalWrite(MUX1_1_A0, HIGH); 
    digitalWrite(MUX1_1_A1, HIGH); 
    digitalWrite(MUX1_1_A2, HIGH); 
    digitalWrite(MUX1_1_A3, HIGH);
    digitalWrite(MUX1_2_EN, LOW); 
    digitalWrite(MUX1_2_A0, LOW); 
    digitalWrite(MUX1_2_A1, LOW); 
    digitalWrite(MUX1_2_A2, LOW);
  }
  else if (WELL == "D5") {
    digitalWrite(MUX1_1_EN, LOW);
    digitalWrite(MUX1_1_A0, LOW); 
    digitalWrite(MUX1_1_A1, LOW); 
    digitalWrite(MUX1_1_A2, LOW); 
    digitalWrite(MUX1_1_A3, LOW);
    digitalWrite(MUX1_2_EN, HIGH); 
    digitalWrite(MUX1_2_A0, HIGH); 
    digitalWrite(MUX1_2_A1, HIGH); 
    digitalWrite(MUX1_2_A2, LOW);
  }
  else if (WELL == "D6") {
    digitalWrite(MUX1_1_EN, LOW);
    digitalWrite(MUX1_1_A0, LOW); 
    digitalWrite(MUX1_1_A1, LOW); 
    digitalWrite(MUX1_1_A2, LOW); 
    digitalWrite(MUX1_1_A3, LOW);
    digitalWrite(MUX1_2_EN, HIGH); 
    digitalWrite(MUX1_2_A0, HIGH); 
    digitalWrite(MUX1_2_A1, HIGH); 
    digitalWrite(MUX1_2_A2, HIGH);
  }
  else if (WELL == "0") {
    digitalWrite(MUX1_1_EN, LOW);
    digitalWrite(MUX1_2_EN, LOW);
  }
}

void IN2(String WELL) {
   //selection puit
  if (WELL == "A1") {
    digitalWrite(MUX2_1_EN, HIGH);
    digitalWrite(MUX2_1_A0, LOW); 
    digitalWrite(MUX2_1_A1, LOW); 
    digitalWrite(MUX2_1_A2, LOW); 
    digitalWrite(MUX2_1_A3, LOW);
    digitalWrite(MUX2_2_EN, LOW); 
    digitalWrite(MUX2_2_A0, LOW); 
    digitalWrite(MUX2_2_A1, LOW); 
    digitalWrite(MUX2_2_A2, LOW);
  }
  else if (WELL == "A2") {
    digitalWrite(MUX2_1_EN, HIGH);
    digitalWrite(MUX2_1_A0, LOW); 
    digitalWrite(MUX2_1_A1, LOW); 
    digitalWrite(MUX2_1_A2, HIGH); 
    digitalWrite(MUX2_1_A3, LOW);
    digitalWrite(MUX2_2_EN, LOW); 
    digitalWrite(MUX2_2_A0, LOW); 
    digitalWrite(MUX2_2_A1, LOW); 
    digitalWrite(MUX2_2_A2, LOW);
  }
  else if (WELL == "A3") {
    digitalWrite(MUX2_1_EN, HIGH);
    digitalWrite(MUX2_1_A0, LOW); 
    digitalWrite(MUX2_1_A1, LOW); 
    digitalWrite(MUX2_1_A2, LOW); 
    digitalWrite(MUX2_1_A3, HIGH);
    digitalWrite(MUX2_2_EN, LOW); 
    digitalWrite(MUX2_2_A0, LOW); 
    digitalWrite(MUX2_2_A1, LOW); 
    digitalWrite(MUX2_2_A2, LOW);
  }
  else if (WELL == "A4") {
    digitalWrite(MUX2_1_EN, HIGH);
    digitalWrite(MUX2_1_A0, LOW); 
    digitalWrite(MUX2_1_A1, LOW); 
    digitalWrite(MUX2_1_A2, HIGH); 
    digitalWrite(MUX2_1_A3, HIGH);
    digitalWrite(MUX2_2_EN, LOW); 
    digitalWrite(MUX2_2_A0, LOW); 
    digitalWrite(MUX2_2_A1, LOW); 
    digitalWrite(MUX2_2_A2, LOW);
  }
  else if (WELL == "A5") {
    digitalWrite(MUX2_1_EN, LOW);
    digitalWrite(MUX2_1_A0, LOW); 
    digitalWrite(MUX2_1_A1, LOW); 
    digitalWrite(MUX2_1_A2, LOW); 
    digitalWrite(MUX2_1_A3, LOW);
    digitalWrite(MUX2_2_EN, HIGH); 
    digitalWrite(MUX2_2_A0, LOW); 
    digitalWrite(MUX2_2_A1, LOW); 
    digitalWrite(MUX2_2_A2, LOW);
  }
  else if (WELL == "A6") {
    digitalWrite(MUX2_1_EN, LOW);
    digitalWrite(MUX2_1_A0, LOW); 
    digitalWrite(MUX2_1_A1, LOW); 
    digitalWrite(MUX2_1_A2, LOW); 
    digitalWrite(MUX2_1_A3, LOW);
    digitalWrite(MUX2_2_EN, HIGH); 
    digitalWrite(MUX2_2_A0, LOW); 
    digitalWrite(MUX2_2_A1, LOW); 
    digitalWrite(MUX2_2_A2, HIGH);
  }
  else if (WELL == "B1") {
    digitalWrite(MUX2_1_EN, HIGH);
    digitalWrite(MUX2_1_A0, HIGH); 
    digitalWrite(MUX2_1_A1, LOW); 
    digitalWrite(MUX2_1_A2, LOW); 
    digitalWrite(MUX2_1_A3, LOW);
    digitalWrite(MUX2_2_EN, LOW); 
    digitalWrite(MUX2_2_A0, LOW); 
    digitalWrite(MUX2_2_A1, LOW); 
    digitalWrite(MUX2_2_A2, LOW);
  }
  else if (WELL == "B2") {
    digitalWrite(MUX2_1_EN, HIGH);
    digitalWrite(MUX2_1_A0, HIGH); 
    digitalWrite(MUX2_1_A1, LOW); 
    digitalWrite(MUX2_1_A2, HIGH); 
    digitalWrite(MUX2_1_A3, LOW);
    digitalWrite(MUX2_2_EN, LOW); 
    digitalWrite(MUX2_2_A0, LOW); 
    digitalWrite(MUX2_2_A1, LOW); 
    digitalWrite(MUX2_2_A2, LOW);
  }
  else if (WELL == "B3") {
    digitalWrite(MUX2_1_EN, HIGH);
    digitalWrite(MUX2_1_A0, HIGH); 
    digitalWrite(MUX2_1_A1, LOW); 
    digitalWrite(MUX2_1_A2, LOW); 
    digitalWrite(MUX2_1_A3, HIGH);
    digitalWrite(MUX2_2_EN, LOW); 
    digitalWrite(MUX2_2_A0, LOW); 
    digitalWrite(MUX2_2_A1, LOW); 
    digitalWrite(MUX2_2_A2, LOW);
  }
  else if (WELL == "B4") {
    digitalWrite(MUX2_1_EN, HIGH);
    digitalWrite(MUX2_1_A0, HIGH); 
    digitalWrite(MUX2_1_A1, LOW); 
    digitalWrite(MUX2_1_A2, HIGH); 
    digitalWrite(MUX2_1_A3, HIGH);
    digitalWrite(MUX2_2_EN, LOW); 
    digitalWrite(MUX2_2_A0, LOW); 
    digitalWrite(MUX2_2_A1, LOW); 
    digitalWrite(MUX2_2_A2, LOW);
  }
  else if (WELL == "B5") {
    digitalWrite(MUX2_1_EN, LOW);
    digitalWrite(MUX2_1_A0, LOW); 
    digitalWrite(MUX2_1_A1, LOW); 
    digitalWrite(MUX2_1_A2, LOW); 
    digitalWrite(MUX2_1_A3, LOW);
    digitalWrite(MUX2_2_EN, HIGH); 
    digitalWrite(MUX2_2_A0, HIGH); 
    digitalWrite(MUX2_2_A1, LOW); 
    digitalWrite(MUX2_2_A2, LOW);
  }
  else if (WELL == "B6") {
    digitalWrite(MUX2_1_EN, LOW);
    digitalWrite(MUX2_1_A0, LOW); 
    digitalWrite(MUX2_1_A1, LOW); 
    digitalWrite(MUX2_1_A2, LOW); 
    digitalWrite(MUX2_1_A3, LOW);
    digitalWrite(MUX2_2_EN, HIGH); 
    digitalWrite(MUX2_2_A0, HIGH); 
    digitalWrite(MUX2_2_A1, LOW); 
    digitalWrite(MUX2_2_A2, HIGH);
  }
  else if (WELL == "C1") {
    digitalWrite(MUX2_1_EN, HIGH);
    digitalWrite(MUX2_1_A0, LOW); 
    digitalWrite(MUX2_1_A1, HIGH); 
    digitalWrite(MUX2_1_A2, LOW); 
    digitalWrite(MUX2_1_A3, LOW);
    digitalWrite(MUX2_2_EN, LOW); 
    digitalWrite(MUX2_2_A0, LOW); 
    digitalWrite(MUX2_2_A1, LOW); 
    digitalWrite(MUX2_2_A2, LOW);
  }
  else if (WELL == "C2") {
    digitalWrite(MUX2_1_EN, HIGH);
    digitalWrite(MUX2_1_A0, LOW); 
    digitalWrite(MUX2_1_A1, HIGH); 
    digitalWrite(MUX2_1_A2, HIGH); 
    digitalWrite(MUX2_1_A3, LOW);
    digitalWrite(MUX2_2_EN, LOW); 
    digitalWrite(MUX2_2_A0, LOW); 
    digitalWrite(MUX2_2_A1, LOW); 
    digitalWrite(MUX2_2_A2, LOW);
  }
  else if (WELL == "C3") {
    digitalWrite(MUX2_1_EN, HIGH);
    digitalWrite(MUX2_1_A0, LOW); 
    digitalWrite(MUX2_1_A1, HIGH); 
    digitalWrite(MUX2_1_A2, LOW); 
    digitalWrite(MUX2_1_A3, HIGH);
    digitalWrite(MUX2_2_EN, LOW); 
    digitalWrite(MUX2_2_A0, LOW); 
    digitalWrite(MUX2_2_A1, LOW); 
    digitalWrite(MUX2_2_A2, LOW);
  }
  else if (WELL == "C4") {
    digitalWrite(MUX2_1_EN, HIGH);
    digitalWrite(MUX2_1_A0, LOW); 
    digitalWrite(MUX2_1_A1, HIGH); 
    digitalWrite(MUX2_1_A2, HIGH); 
    digitalWrite(MUX2_1_A3, HIGH);
    digitalWrite(MUX2_2_EN, LOW); 
    digitalWrite(MUX2_2_A0, LOW); 
    digitalWrite(MUX2_2_A1, LOW); 
    digitalWrite(MUX2_2_A2, LOW);
  }
  else if (WELL == "C5") {
    digitalWrite(MUX2_1_EN, LOW);
    digitalWrite(MUX2_1_A0, LOW); 
    digitalWrite(MUX2_1_A1, LOW); 
    digitalWrite(MUX2_1_A2, LOW); 
    digitalWrite(MUX2_1_A3, LOW);
    digitalWrite(MUX2_2_EN, HIGH); 
    digitalWrite(MUX2_2_A0, LOW); 
    digitalWrite(MUX2_2_A1, HIGH); 
    digitalWrite(MUX2_2_A2, LOW);
  }
  else if (WELL == "C6") {
    digitalWrite(MUX2_1_EN, LOW);
    digitalWrite(MUX2_1_A0, LOW); 
    digitalWrite(MUX2_1_A1, LOW); 
    digitalWrite(MUX2_1_A2, LOW); 
    digitalWrite(MUX2_1_A3, LOW);
    digitalWrite(MUX2_2_EN, HIGH); 
    digitalWrite(MUX2_2_A0, LOW); 
    digitalWrite(MUX2_2_A1, HIGH); 
    digitalWrite(MUX2_2_A2, HIGH);
  }
  else if (WELL == "D1") {
    digitalWrite(MUX2_1_EN, HIGH);
    digitalWrite(MUX2_1_A0, HIGH); 
    digitalWrite(MUX2_1_A1, HIGH); 
    digitalWrite(MUX2_1_A2, LOW); 
    digitalWrite(MUX2_1_A3, LOW);
    digitalWrite(MUX2_2_EN, LOW); 
    digitalWrite(MUX2_2_A0, LOW); 
    digitalWrite(MUX2_2_A1, LOW); 
    digitalWrite(MUX2_2_A2, LOW);
  }
  else if (WELL == "D2") {
    digitalWrite(MUX2_1_EN, HIGH);
    digitalWrite(MUX2_1_A0, HIGH); 
    digitalWrite(MUX2_1_A1, HIGH); 
    digitalWrite(MUX2_1_A2, HIGH); 
    digitalWrite(MUX2_1_A3, LOW);
    digitalWrite(MUX2_2_EN, LOW); 
    digitalWrite(MUX2_2_A0, LOW); 
    digitalWrite(MUX2_2_A1, LOW); 
    digitalWrite(MUX2_2_A2, LOW);
  }
  else if (WELL == "D3") {
    digitalWrite(MUX2_1_EN, HIGH);
    digitalWrite(MUX2_1_A0, HIGH); 
    digitalWrite(MUX2_1_A1, HIGH); 
    digitalWrite(MUX2_1_A2, LOW); 
    digitalWrite(MUX2_1_A3, HIGH);
    digitalWrite(MUX2_2_EN, LOW); 
    digitalWrite(MUX2_2_A0, LOW); 
    digitalWrite(MUX2_2_A1, LOW); 
    digitalWrite(MUX2_2_A2, LOW);
  }
  else if (WELL == "D4") {
    digitalWrite(MUX2_1_EN, HIGH);
    digitalWrite(MUX2_1_A0, HIGH); 
    digitalWrite(MUX2_1_A1, HIGH); 
    digitalWrite(MUX2_1_A2, HIGH); 
    digitalWrite(MUX2_1_A3, HIGH);
    digitalWrite(MUX2_2_EN, LOW); 
    digitalWrite(MUX2_2_A0, LOW); 
    digitalWrite(MUX2_2_A1, LOW); 
    digitalWrite(MUX2_2_A2, LOW);
  }
  else if (WELL == "D5") {
    digitalWrite(MUX2_1_EN, LOW);
    digitalWrite(MUX2_1_A0, LOW); 
    digitalWrite(MUX2_1_A1, LOW); 
    digitalWrite(MUX2_1_A2, LOW); 
    digitalWrite(MUX2_1_A3, LOW);
    digitalWrite(MUX2_2_EN, HIGH); 
    digitalWrite(MUX2_2_A0, HIGH); 
    digitalWrite(MUX2_2_A1, HIGH); 
    digitalWrite(MUX2_2_A2, LOW);
  }
  else if (WELL == "D6") {
    digitalWrite(MUX2_1_EN, LOW);
    digitalWrite(MUX2_1_A0, LOW); 
    digitalWrite(MUX2_1_A1, LOW); 
    digitalWrite(MUX2_1_A2, LOW); 
    digitalWrite(MUX2_1_A3, LOW);
    digitalWrite(MUX2_2_EN, HIGH); 
    digitalWrite(MUX2_2_A0, HIGH); 
    digitalWrite(MUX2_2_A1, HIGH); 
    digitalWrite(MUX2_2_A2, HIGH);
  }
  else if (WELL == "0") {
    digitalWrite(MUX2_1_EN, LOW);
    digitalWrite(MUX2_2_EN, LOW);
  }
}

void setup() {

// Initialiser le Serial
  Serial.begin(9600);

 pinMode(SW_BP1, OUTPUT);
 pinMode(SW_BP2, OUTPUT);
 pinMode(MUX1_1_EN, OUTPUT);
 pinMode(MUX1_2_EN, OUTPUT);
 pinMode(MUX2_1_EN, OUTPUT);
 pinMode(MUX2_2_EN, OUTPUT);
 pinMode(MUX1_1_A0, OUTPUT);
 pinMode(MUX1_1_A1, OUTPUT);
 pinMode(MUX1_1_A2, OUTPUT);
 pinMode(MUX1_1_A3, OUTPUT); 
 pinMode(MUX1_2_A0, OUTPUT); 
 pinMode(MUX1_2_A1, OUTPUT); 
 pinMode(MUX1_2_A2, OUTPUT); 
 pinMode(MUX2_1_A0, OUTPUT); 
 pinMode(MUX2_1_A1, OUTPUT); 
 pinMode(MUX2_1_A2, OUTPUT); 
 pinMode(MUX2_1_A3, OUTPUT); 
 pinMode(MUX2_2_A0, OUTPUT); 
 pinMode(MUX2_2_A1, OUTPUT); 
 pinMode(MUX2_2_A2, OUTPUT); 

 digitalWrite(SW_BP1, LOW);
 digitalWrite(SW_BP2, LOW);
 digitalWrite(MUX1_1_EN, LOW);
 digitalWrite(MUX1_2_EN, LOW);
 digitalWrite(MUX2_1_EN, LOW);
 digitalWrite(MUX2_2_EN, LOW); 
 digitalWrite(MUX1_1_A0, LOW); 
 digitalWrite(MUX1_1_A1, LOW); 
 digitalWrite(MUX1_1_A2, LOW); 
 digitalWrite(MUX1_1_A3, LOW); 
 digitalWrite(MUX1_2_A0, LOW); 
 digitalWrite(MUX1_2_A1, LOW); 
 digitalWrite(MUX1_2_A2, LOW); 
 digitalWrite(MUX2_1_A0, LOW); 
 digitalWrite(MUX2_1_A1, LOW); 
 digitalWrite(MUX2_1_A2, LOW); 
 digitalWrite(MUX2_1_A3, LOW); 
 digitalWrite(MUX2_2_A0, LOW); 
 digitalWrite(MUX2_2_A1, LOW); 
 digitalWrite(MUX2_2_A2, LOW);

Serial.println("=== Système de contrôle MUX ===");
  Serial.println("Format de commande: [IN] [BP] [WELL]");
  Serial.println("Exemples:");
  Serial.println("  1 1 D5  -> IN(1) BP(1) WELL(D5)");
  Serial.println("  2 0 C4  -> IN(2) BP(0) WELL(C4)");
  Serial.println("IN(stim1 ou stim2): 1 ou 2");
  Serial.println("BP(byPass): 0 ou 1");
  Serial.println("WELL: A1-A6, B1-B6, C1-C6, D1-D6");
  Serial.println("================================");

}

void loop() {
if (Serial.available() > 0) {
    String input = Serial.readStringUntil('\n');
    input.trim();
    
    // Parser la commande "BP value WELL"
    int firstSpace = input.indexOf(' ');
    int secondSpace = input.indexOf(' ', firstSpace + 1);
    
    if (firstSpace > 0 && secondSpace > 0) {
      String bpStr = input.substring(0, firstSpace);
      String valueStr = input.substring(firstSpace + 1, secondSpace);
      String well = input.substring(secondSpace + 1);
      
      int bp = bpStr.toInt();
      int value = valueStr.toInt();
      
      // Vérifier la validité
      if ((bp == 1 || bp == 2) && (value == 0 || value == 1)) {
        // Vérifier le WELL
        char firstChar = well.charAt(0);
        if ((firstChar == 'A' || firstChar == 'B' || 
             firstChar == 'C' || firstChar == 'D') && well.length() == 2) {
          
          Serial.print("Commande reçue: ");
          Serial.println(input);
          
          // Appeler les fonctions appropriées
          if (bp == 1) {
            BP1(value);
            IN1(well);
          } else {
            BP2(value);
            IN2(well);
          }
          
        } else {
          Serial.println("Erreur: WELL invalide (A1-A6, B1-B6, C1-C6, D1-D6)");
        }
      } else {
        Serial.println("Erreur: BP doit être 1 ou 2, valeur doit être 0 ou 1");
      }
    } else {
      Serial.println("Erreur: Format incorrect. Utilisez: BP value WELL");
      Serial.println("Exemple: 1 1 D5");
    }
  }
}
