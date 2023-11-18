{ python }:
python.pkgs.buildPythonPackage rec {
  name = "mk2";
  format = "pyproject";
  src = ./.;
  nativeBuildInputs = with python.pkgs; [
    setuptools
  ];
  propagatedBuildInputs = with python.pkgs; [
    pyserial
    pyserial-asyncio
  ];
  nativeCheckInputs = with python.pkgs; [ pytestCheckHook ];
}
