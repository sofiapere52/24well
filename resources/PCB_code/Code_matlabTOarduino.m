clear all;
clc;

port = "COM6";  

% Créer la connexion série
arduino = serialport(port, 9600);
% Configurer le terminateur (correspond à Serial.println dans Arduino)
configureTerminator(arduino, "LF");
% Vider le buffer
flush(arduino);

pause(3);

% Création Message
% Choix stimulateur : 1/2
Stim=1;
% By pass filtre : 1/0 
ByPass=1;
% Choix des puits A->D et 1->6
Lettre="B";
Numero=3;
Well=Lettre+string(Numero);

Commande=string(Stim) + " " + string(ByPass) + " " + Well

% Envoyer la commande
writeline(arduino, Commande);

% % Pour lire un retour
% reponse = readline(arduino);
% disp("Retour Arduino : " + reponse);

% % Fermer la connexion
% clear arduino;
% disp('Connexion fermée');

